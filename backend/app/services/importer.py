"""
Excel importer for InvestmentTracker.
Parses Inversiones.xlsx and populates the database.
"""
import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.annual_summary import AnnualSummary
from app.models.provento import Provento
from app.models.quote import Quote


# Columns in Resumen that belong to PortfolioSnapshot (not instruments)
SNAPSHOT_COLUMNS = {
    "Total", "Incremento", "HSBC Total", "Bradesco Total", "XP BR Total",
    "XP US Total", "Santander Total", "Inter Total", "Brasil Total",
    "FGTS", "PREV", "Total + Prev", "Total - B3", "USA Total",
    "Dolar", "Total Dolar", "Total Dolar + Prev",
}

MONTH_MAP = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
    "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
    "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12,
}


def normalize_date(val: Any) -> Optional[date]:
    """Normalize any date-like value to the first day of its month."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        if isinstance(val, (datetime, pd.Timestamp)):
            return date(val.year, val.month, 1)
        if isinstance(val, date):
            return date(val.year, val.month, 1)
        if isinstance(val, str):
            parsed = pd.to_datetime(val, dayfirst=True)
            return date(parsed.year, parsed.month, 1)
    except Exception:
        return None
    return None


def safe_float(val: Any) -> Optional[float]:
    """Convert value to float, return None for invalid/NaN."""
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    try:
        f = float(val)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _is_exterior(name: str, custodian: str) -> bool:
    """Return True if the instrument is custodied abroad."""
    n = name.upper()
    c = custodian.upper()
    return (
        any(k in n for k in ["USA", "CITI", "DOLLAR", "DOLAR", "MDQ", "DEITRES", "SUNNYHUB"])
        or c in ["CITI", "CITI USA", "ALLARIA", "MDQ", "DEITRES"]
    )


def classify_instrument_type(name: str, custodian: str) -> str:
    """Classify instrument type based on name patterns."""
    n = name.upper()

    if any(k in n for k in ["PREV", "PREVIDENCIA", "PREVIDÊNCIA"]):
        return "previdencia"
    if "FGTS" in n:
        return "fgts"
    if any(n.startswith(k) for k in ["PETR", "VALE", "ITUB", "BBAS", "ABEV"]) or (
        len(n) == 5 and n[-1].isdigit() and not any(k in n for k in ["CDB", "LCA", "LCI", "CRI", "CRA", "DEB"])
    ):
        return "accion"
    if any(k in n for k in ["BVMF", "B3SA", "B3 SA", "ETF"]):
        return "accion"
    if any(n.endswith(k) for k in ["11", "12"]) and len(n.split()) == 1:
        return "fii"
    if any(k in n for k in ["XPLG", "XPML", "HGLG", "KNRI", "VISC", "RECT"]):
        return "fii"
    if any(k in n for k in ["CDB", "LCA", "LCI", "NTNB", "NTN-B", "LFT", "LTN",
                              "CRI", "CRA", "DEB", "TESOURO", "TREASURY", "TD SELIC",
                              "IPCA +", "LIG", "LETRA", "US TRES", "US EMBRAER",
                              "US MARFRIG", "US PETRO", "US REDE", "AL30", "MEP"]):
        return "renta_fija"
    if any(k in n for k in ["FIC", "FICFI", "FIM", "FI RF", "FI DI", "FUNDO",
                              "TREND", "PORTO DI", "ADAM", "WESTERN", "PIMCO",
                              "POLO", "VERDE", "MODAL", "BAHIA", "ENDURANCE",
                              "BTG EXPLORER", "MACRO", "SELECTION", "CAMBIAL"]):
        return "fundo"
    return "outro"


def get_or_create_instrument(db: Session, name: str, custodian: str) -> Instrument:
    """Get existing instrument or create a new one."""
    inst = db.query(Instrument).filter_by(name=name, custodian=custodian).first()
    if not inst:
        is_ext = _is_exterior(name, custodian)
        inst = Instrument(
            name=name,
            custodian=custodian,
            type=classify_instrument_type(name, custodian),
            location="exterior" if is_ext else "brasil",
            currency="USD" if is_ext else "BRL",
        )
        db.add(inst)
        db.flush()
    return inst


def upsert_position(db: Session, instrument_id: int, pos_date: date, data: dict) -> bool:
    """Insert or update a MonthlyPosition. Returns True if created, False if updated."""
    pos = db.query(MonthlyPosition).filter_by(
        instrument_id=instrument_id, date=pos_date
    ).first()
    if pos:
        for k, v in data.items():
            setattr(pos, k, v)
        return False
    else:
        pos = MonthlyPosition(instrument_id=instrument_id, date=pos_date, **data)
        db.add(pos)
        return True


def import_saldos(df: pd.DataFrame, db: Session, warnings: list, errors: list) -> int:
    """Parse Hoja Saldos. Headers in row 1 (0-indexed), data from row 2."""
    # pandas read with header=1 gives us the correct structure
    count = 0
    for idx, row in df.iterrows():
        try:
            mes = row.get("Mes")
            banco = str(row.get("Banco", "") or "").strip()
            fondo = str(row.get("Fondo", "") or "").strip()

            if not banco or not fondo or banco == "nan" or fondo == "nan":
                continue

            pos_date = normalize_date(mes)
            if not pos_date:
                warnings.append(f"Saldos row {idx}: fecha invalida '{mes}', omitida")
                continue

            saldo_brl = safe_float(row.get("Saldo BRL"))
            if saldo_brl is None:
                continue  # Skip rows without balance

            inst = get_or_create_instrument(db, fondo, banco)

            balance_usd = safe_float(row.get("Saldo USD"))
            usd_rate = safe_float(row.get("Cot USD"))

            data = {
                "balance_brl": saldo_brl,
                "balance_usd": balance_usd,
                "usd_rate": usd_rate,
                "applications": safe_float(row.get("Aplicaciones")),
                "redemptions": safe_float(row.get("Rescates")),
                "calculated_balance": safe_float(row.get("Saldo calculado")),
                "previous_balance": safe_float(row.get("Saldo anterior")),
                "gain": safe_float(row.get("Ganancia")),
                "gain_pct": safe_float(row.get("Ganancia (%)")),
                "proventos": safe_float(row.get("Proventos")),
                "avg_price": safe_float(row.get("Preço médio")),
            }

            if inst.type in ("accion", "fii"):
                data["quantity"] = balance_usd
                data["unit_price"] = usd_rate

            upsert_position(db, inst.id, pos_date, data)
            count += 1
        except Exception as e:
            errors.append(f"Saldos row {idx}: {str(e)}")
    return count


def import_resumen(df: pd.DataFrame, db: Session, warnings: list, errors: list) -> int:
    """Parse Hoja Resumen. Headers in row 0, data from row 1."""
    count = 0
    for idx, row in df.iterrows():
        try:
            snap_date = normalize_date(row.get("Fechas") or row.iloc[0])
            if not snap_date:
                continue

            snap = db.query(PortfolioSnapshot).filter_by(date=snap_date).first()
            if not snap:
                snap = PortfolioSnapshot(date=snap_date)
                db.add(snap)

            snap.total_brl = safe_float(row.get("Total"))
            snap.total_with_prev = safe_float(row.get("Total + Prev"))
            snap.total_without_b3 = safe_float(row.get("Total - B3"))
            snap.total_usd = safe_float(row.get("Total Dolar"))
            snap.total_usd_with_prev = safe_float(row.get("Total Dolar + Prev"))
            snap.usd_rate = safe_float(row.get("Dolar"))
            snap.monthly_change_pct = safe_float(row.get("Incremento"))
            snap.hsbc_total = safe_float(row.get("HSBC Total"))
            snap.bradesco_total = safe_float(row.get("Bradesco Total"))
            snap.xp_br_total = safe_float(row.get("XP BR Total"))
            snap.xp_us_total = safe_float(row.get("XP US Total"))
            snap.santander_total = safe_float(row.get("Santander Total"))
            snap.inter_total = safe_float(row.get("Inter Total"))
            snap.brasil_total = safe_float(row.get("Brasil Total"))
            snap.fgts = safe_float(row.get("FGTS"))
            snap.prev = safe_float(row.get("PREV"))
            snap.usa_total = safe_float(row.get("USA Total"))
            count += 1
        except Exception as e:
            errors.append(f"Resumen row {idx}: {str(e)}")
    return count


def import_cotizaciones(df: pd.DataFrame, db: Session, warnings: list, errors: list) -> int:
    """Parse Hoja Cotizaciones. Headers in row 0."""
    count = 0
    for idx, row in df.iterrows():
        try:
            q_date = normalize_date(row.get("Fechas") or row.iloc[0])
            if not q_date:
                continue
            usd_brl = safe_float(row.get("Dolar"))
            bvmf3 = safe_float(row.get("BVMF3"))

            quote = db.query(Quote).filter_by(date=q_date).first()
            if quote:
                quote.usd_brl = usd_brl
                quote.bvmf3_price = bvmf3
            else:
                db.add(Quote(date=q_date, usd_brl=usd_brl, bvmf3_price=bvmf3))
            count += 1
        except Exception as e:
            errors.append(f"Cotizaciones row {idx}: {str(e)}")
    return count


def import_totales(df: pd.DataFrame, db: Session, warnings: list, errors: list) -> int:
    """Parse Hoja Totales. Headers in row 1 (0-indexed), data from row 2."""
    count = 0
    for idx, row in df.iterrows():
        try:
            ano_raw = row.get("Ano")
            if ano_raw is None or (isinstance(ano_raw, str) and "total" in ano_raw.lower()):
                continue
            ano_date = normalize_date(ano_raw)
            if not ano_date:
                continue

            year = ano_date.year
            existing = db.query(AnnualSummary).filter_by(year=year).first()
            if existing:
                existing.total = safe_float(row.get("Total"))
                existing.diff = safe_float(row.get("Dif"))
                existing.gain = safe_float(row.get("Ganancia"))
                existing.net_flow = safe_float(row.get("Aplicaciones/Rescates"))
                existing.year_date = ano_date
            else:
                db.add(AnnualSummary(
                    year=year,
                    year_date=ano_date,
                    total=safe_float(row.get("Total")),
                    diff=safe_float(row.get("Dif")),
                    gain=safe_float(row.get("Ganancia")),
                    net_flow=safe_float(row.get("Aplicaciones/Rescates")),
                ))
            count += 1
        except Exception as e:
            errors.append(f"Totales row {idx}: {str(e)}")
    return count


def import_ranking(df_raw: pd.DataFrame, db: Session, warnings: list, errors: list) -> int:
    """
    Parse Hoja Ranking.
    Headers in row 3 (0-indexed), data from row 4, table starts at column 5.
    """
    count = 0
    try:
        # Extract the sub-table starting at col 5, header at row 3
        sub = df_raw.iloc[3:, 5:].reset_index(drop=True)
        # Row 0 is headers, row 1+ is data
        headers = sub.iloc[0].tolist()
        data = sub.iloc[1:].copy()
        data.columns = range(len(data.columns))

        # Map header positions
        col_map = {}
        for i, h in enumerate(headers):
            if pd.isna(h):
                continue
            h_str = str(h).strip()
            col_map[h_str] = i

        fondo_col = col_map.get("Fondo", 0)
        venc_col = col_map.get("Venc", 1)
        saldo_col = col_map.get("Saldo", 2)
        porc_col = col_map.get("Porc", 3)
        ret_1m_col = col_map.get("Ultimo mes", 4)
        rank_1m_col = col_map.get("Ranking ult mes", 5)
        ret_3m_col = col_map.get("Últimos 3 meses", 6)
        rank_3m_col = 7
        ret_6m_col = col_map.get("Últimos 6 meses", 8)
        rank_6m_col = 9
        ret_12m_col = col_map.get("Ultimo año", 10)
        rank_12m_col = 11

        for idx, row in data.iterrows():
            try:
                fondo_raw = row.iloc[fondo_col] if fondo_col < len(row) else None
                if fondo_raw is None or (isinstance(fondo_raw, float) and np.isnan(fondo_raw)):
                    continue
                fondo = str(fondo_raw).strip()
                if not fondo:
                    continue

                # Find instrument by name (ignoring custodian)
                inst = db.query(Instrument).filter(Instrument.name == fondo).first()
                if not inst:
                    warnings.append(f"Ranking: instrumento '{fondo}' no encontrado en BD, omitido")
                    continue

                def get_col(col_idx):
                    if col_idx < len(row):
                        return safe_float(row.iloc[col_idx])
                    return None

                inst.liquidity = str(row.iloc[venc_col]).strip() if venc_col < len(row) and not pd.isna(row.iloc[venc_col]) else inst.liquidity
                inst.current_balance_brl = get_col(saldo_col)
                inst.portfolio_pct = get_col(porc_col)
                inst.return_1m = get_col(ret_1m_col)
                inst.rank_1m = int(get_col(rank_1m_col)) if get_col(rank_1m_col) is not None else None
                inst.return_3m = get_col(ret_3m_col)
                inst.rank_3m = int(get_col(rank_3m_col)) if get_col(rank_3m_col) is not None else None
                inst.return_6m = get_col(ret_6m_col)
                inst.rank_6m = int(get_col(rank_6m_col)) if get_col(rank_6m_col) is not None else None
                inst.return_12m = get_col(ret_12m_col)
                inst.rank_12m = int(get_col(rank_12m_col)) if get_col(rank_12m_col) is not None else None

                count += 1
            except Exception as e:
                errors.append(f"Ranking row {idx}: {str(e)}")
    except Exception as e:
        errors.append(f"Ranking sheet error: {str(e)}")
    return count


def import_proventos(df_raw: pd.DataFrame, db: Session, warnings: list, errors: list) -> int:
    """
    Parse Hoja Proventos.
    Headers in row 3 (0-indexed), data from row 4, table starts at column 5.
    """
    count = 0
    try:
        sub = df_raw.iloc[3:, 5:].reset_index(drop=True)
        headers = sub.iloc[0].tolist()
        data = sub.iloc[1:].copy()
        data.columns = range(len(data.columns))

        # Build column index
        col_map = {}
        for i, h in enumerate(headers):
            if h is None or (isinstance(h, float) and np.isnan(h)):
                continue
            if isinstance(h, datetime):
                # Monthly column stored as date
                col_map[f"month_{h.month}"] = i
            else:
                h_str = str(h).strip()
                col_map[h_str] = i

        fondo_col = col_map.get("Fondo", 0)
        saldo_col = col_map.get("Saldo", 1)

        # Find annual columns like "Proventos 2026", "Proventos 2025"...
        annual_cols = {}
        for h, i in col_map.items():
            if h.startswith("Proventos "):
                try:
                    yr = int(h.replace("Proventos ", ""))
                    annual_cols[yr] = i
                except ValueError:
                    pass

        for idx, row in data.iterrows():
            try:
                fondo_raw = row.iloc[fondo_col] if fondo_col < len(row) else None
                if fondo_raw is None or (isinstance(fondo_raw, float) and np.isnan(fondo_raw)):
                    continue
                fondo = str(fondo_raw).strip()
                if not fondo:
                    continue

                inst = db.query(Instrument).filter(Instrument.name == fondo).first()
                if not inst:
                    warnings.append(f"Proventos: instrumento '{fondo}' no encontrado, omitido")
                    continue

                # Annual proventos
                for yr, col_idx in annual_cols.items():
                    amt = safe_float(row.iloc[col_idx]) if col_idx < len(row) else None
                    if amt is not None:
                        _upsert_provento(db, inst.id, yr, None, amt)
                        count += 1

                # Monthly proventos (current year)
                for m_key, col_idx in col_map.items():
                    if not m_key.startswith("month_"):
                        continue
                    month_num = int(m_key.replace("month_", ""))
                    amt = safe_float(row.iloc[col_idx]) if col_idx < len(row) else None
                    if amt is not None:
                        # Determine year from context - use current year in headers
                        # Find year from annual column keys (max year = current)
                        current_year = max(annual_cols.keys()) if annual_cols else datetime.now().year
                        _upsert_provento(db, inst.id, current_year, month_num, amt)
                        count += 1
            except Exception as e:
                errors.append(f"Proventos row {idx}: {str(e)}")
    except Exception as e:
        errors.append(f"Proventos sheet error: {str(e)}")
    return count


def _upsert_provento(db: Session, instrument_id: int, year: int, month: Optional[int], amount: float):
    """Insert or update a Provento record."""
    prov = db.query(Provento).filter_by(
        instrument_id=instrument_id, year=year, month=month
    ).first()
    if prov:
        prov.amount = amount
    else:
        db.add(Provento(instrument_id=instrument_id, year=year, month=month, amount=amount))


def update_instrument_statuses(db: Session):
    """Update instrument status based on recent positions."""
    from sqlalchemy import func
    instruments = db.query(Instrument).all()

    # Get the last 3 dates available
    last_dates = (
        db.query(MonthlyPosition.date)
        .distinct()
        .order_by(MonthlyPosition.date.desc())
        .limit(3)
        .all()
    )
    last_dates = [d[0] for d in last_dates]

    for inst in instruments:
        recent = (
            db.query(MonthlyPosition)
            .filter(
                MonthlyPosition.instrument_id == inst.id,
                MonthlyPosition.date.in_(last_dates),
            )
            .all()
        )
        any_pos = db.query(MonthlyPosition).filter_by(instrument_id=inst.id).first()

        if not any_pos:
            inst.status = "sin_datos"
        elif all(
            (p.balance_brl is None or p.balance_brl == 0) for p in recent
        ) and len(recent) > 0:
            inst.status = "cerrado"
        else:
            inst.status = "activo"


def import_excel(filepath: str, db: Session) -> dict:
    """
    Main entry point for importing Inversiones.xlsx.
    Returns a report dict with counts, warnings, and errors.
    """
    warnings = []
    errors = []
    report = {
        "instruments": 0,
        "positions": 0,
        "snapshots": 0,
        "annual": 0,
        "proventos": 0,
        "quotes": 0,
        "ranking": 0,
        "warnings": warnings,
        "errors": errors,
    }

    xls = pd.ExcelFile(filepath)

    # ---- Saldos ----
    if "Saldos" in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name="Saldos", header=1)
            prev_count = db.query(Instrument).count()
            report["positions"] = import_saldos(df, db, warnings, errors)
            db.flush()
            report["instruments"] = db.query(Instrument).count() - prev_count
        except Exception as e:
            errors.append(f"Error leyendo Saldos: {str(e)}")

    # ---- Resumen ----
    if "Resumen" in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name="Resumen", header=0)
            report["snapshots"] = import_resumen(df, db, warnings, errors)
        except Exception as e:
            errors.append(f"Error leyendo Resumen: {str(e)}")

    # ---- Cotizaciones ----
    if "Cotizaciones" in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name="Cotizaciones", header=0)
            report["quotes"] = import_cotizaciones(df, db, warnings, errors)
        except Exception as e:
            errors.append(f"Error leyendo Cotizaciones: {str(e)}")

    # ---- Totales ----
    if "Totales" in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name="Totales", header=1)
            report["annual"] = import_totales(df, db, warnings, errors)
        except Exception as e:
            errors.append(f"Error leyendo Totales: {str(e)}")

    # ---- Ranking ----
    if "Ranking" in xls.sheet_names:
        try:
            df_raw = pd.read_excel(xls, sheet_name="Ranking", header=None)
            report["ranking"] = import_ranking(df_raw, db, warnings, errors)
        except Exception as e:
            errors.append(f"Error leyendo Ranking: {str(e)}")

    # ---- Proventos ----
    if "Proventos" in xls.sheet_names:
        try:
            df_raw = pd.read_excel(xls, sheet_name="Proventos", header=None)
            report["proventos"] = import_proventos(df_raw, db, warnings, errors)
        except Exception as e:
            errors.append(f"Error leyendo Proventos: {str(e)}")

    # Update instrument statuses
    update_instrument_statuses(db)

    # Backfill balance_usd = balance_brl / usd_rate for positions missing it
    db.execute(
        """
        UPDATE monthly_positions
        SET balance_usd = ROUND(balance_brl / ps.usd_rate, 2)
        FROM (SELECT date, usd_rate FROM portfolio_snapshots WHERE usd_rate IS NOT NULL AND usd_rate > 0) ps
        WHERE monthly_positions.date = ps.date
          AND monthly_positions.balance_usd IS NULL
          AND monthly_positions.balance_brl IS NOT NULL
          AND monthly_positions.balance_brl > 0
        """
    )

    db.commit()
    return report
