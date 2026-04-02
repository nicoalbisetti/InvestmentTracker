import io
import math
import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.instrument import Instrument
from app.models.provento_forecast import ProventoForecast

router = APIRouter(prefix="/api/proventos/forecast", tags=["provento_forecast"])

TYPE_ORDER = ["accion", "fii", "renta_fija", "fundo", "previdencia", "prestamos", "saving", "fgts", "outro"]
MONTHS = list(range(1, 13))


@router.get("")
def get_forecast(
    year: int = Query(default=None),
    type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Returns instruments with pays_dividends=True and their forecast amounts per month."""
    target_year = year or date.today().year

    query = db.query(Instrument).filter(
        Instrument.pays_dividends == True,
        Instrument.status == "activo",
    )
    if type:
        query = query.filter(Instrument.type == type)
    instruments = query.all()

    # Load all forecast rows for this year
    inst_ids = [i.id for i in instruments]
    rows = (
        db.query(ProventoForecast)
        .filter(ProventoForecast.instrument_id.in_(inst_ids), ProventoForecast.year == target_year)
        .all()
    )
    forecast_map: dict[tuple, float] = {(r.instrument_id, r.month): r.amount for r in rows}

    items = []
    for inst in instruments:
        months = {m: forecast_map.get((inst.id, m)) for m in MONTHS}
        total = sum(v for v in months.values() if v)
        items.append({
            "id": inst.id,
            "name": inst.name,
            "type": inst.type,
            "location": inst.location,
            "custodian": inst.custodian,
            "months": months,
            "total": total,
        })

    LOCATION_ORDER = ["brasil", "exterior"]
    items.sort(key=lambda x: (
        LOCATION_ORDER.index(x["location"]) if x["location"] in LOCATION_ORDER else 99,
        TYPE_ORDER.index(x["type"]) if x["type"] in TYPE_ORDER else 99,
        x["name"].lower(),
    ))

    # Column totals
    month_totals = {m: sum(row["months"].get(m) or 0 for row in items) for m in MONTHS}
    grand_total = sum(month_totals.values())

    return {
        "year": target_year,
        "items": items,
        "month_totals": month_totals,
        "grand_total": grand_total,
    }


@router.patch("/{instrument_id}/{year}/{month}")
def upsert_forecast(
    instrument_id: int,
    year: int,
    month: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Upsert a forecast cell. Pass amount=null or amount=0 to delete."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Mes inválido")

    amount = payload.get("amount")

    existing = (
        db.query(ProventoForecast)
        .filter_by(instrument_id=instrument_id, year=year, month=month)
        .first()
    )

    if amount is None or amount == 0:
        if existing:
            db.delete(existing)
            db.commit()
        return {"deleted": True}

    if existing:
        existing.amount = float(amount)
    else:
        db.add(ProventoForecast(instrument_id=instrument_id, year=year, month=month, amount=float(amount)))
    db.commit()
    return {"instrument_id": instrument_id, "year": year, "month": month, "amount": float(amount)}


# ─── Month name mapping (ES + PT variants) ────────────────────────────────────

_MONTH_MAP: dict[str, int] = {
    "enero": 1, "jan": 1, "janeiro": 1,
    "febrero": 2, "feb": 2, "fevereiro": 2,
    "marzo": 3, "mar": 3, "março": 3,
    "abril": 4, "abr": 4,
    "mayo": 5, "may": 5, "maio": 5,
    "junio": 6, "jun": 6, "junho": 6,
    "julio": 7, "jul": 7, "julho": 7,
    "agosto": 8, "ago": 8,
    "septiembre": 9, "sep": 9, "setembro": 9, "set": 9,
    "octubre": 10, "oct": 10, "outubro": 10, "out": 10,
    "noviembre": 11, "nov": 11, "novembro": 11,
    "diciembre": 12, "dec": 12, "dezembro": 12, "dic": 12,
}


def _parse_num(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and math.isnan(val):
            return None
        return float(val)
    s = str(val).strip()
    if not s or s in ("-", "nan", "None", ""):
        return None
    # Brazilian format: "1.234,56" → 1234.56
    cleaned = s.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


@router.post("/import/preview")
async def preview_forecast_import(
    file: UploadFile = File(...),
    year: int = Form(...),
    db: Session = Depends(get_db),
):
    """
    Parse a forecast Excel (columns: Activo + one per month) and return a preview
    of what would be upserted, including instrument match status per row.
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=422, detail="El archivo debe ser .xlsx o .xls")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="El archivo está vacío")

    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=0)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"No se pudo leer el Excel: {e}")

    if df.empty or len(df.columns) < 2:
        raise HTTPException(status_code=422, detail="El archivo no tiene el formato esperado (mínimo 2 columnas)")

    # Map column index → month number
    col_month: dict[int, int] = {}
    for col_idx, col_name in enumerate(df.columns):
        if col_idx == 0:
            continue  # instrument column

        # pandas may parse month-name headers as datetime objects when the cell
        # is formatted as a date in Excel (e.g. "Abril" → datetime(2026,4,1))
        import datetime as _dt
        if isinstance(col_name, (_dt.datetime, _dt.date)):
            col_month[col_idx] = col_name.month
            continue

        name_clean = str(col_name).strip().lower().split()[0]
        # Try numeric
        try:
            n = int(name_clean)
            if 1 <= n <= 12:
                col_month[col_idx] = n
            continue
        except ValueError:
            pass
        m = _MONTH_MAP.get(name_clean)
        if m:
            col_month[col_idx] = m

    if not col_month:
        raise HTTPException(
            status_code=422,
            detail="No se encontraron columnas de meses. Usar nombres como 'Enero', 'Febrero'... o números 1-12."
        )

    warnings: list[str] = []
    rows = []

    for _, row in df.iterrows():
        activo_raw = row.iloc[0]
        if not activo_raw or (isinstance(activo_raw, float) and math.isnan(activo_raw)):
            continue
        activo_str = str(activo_raw).strip()
        if not activo_str:
            continue

        # Instrument matching: try ticker exact → name ilike
        ticker_part = activo_str.split(" - ")[0].strip() if " - " in activo_str else activo_str
        inst = db.query(Instrument).filter(Instrument.ticker == ticker_part).first()
        status = "matched"
        candidates: list[dict] = []
        instrument_id = None
        instrument_name = None

        if inst:
            instrument_id = inst.id
            instrument_name = inst.name
        else:
            # name search
            keyword = ticker_part if len(ticker_part) >= 3 else activo_str[:20]
            results = db.query(Instrument).filter(Instrument.name.ilike(f"%{keyword}%")).all()
            if len(results) == 1:
                instrument_id = results[0].id
                instrument_name = results[0].name
            elif len(results) > 1:
                status = "ambiguous"
                candidates = [{"id": r.id, "name": r.name, "ticker": r.ticker} for r in results[:5]]
            else:
                status = "no_match"
                warnings.append(f"Sin match para '{activo_str}'")

        months: dict[int, Optional[float]] = {}
        for col_idx, month_num in col_month.items():
            val = _parse_num(row.iloc[col_idx]) if col_idx < len(row) else None
            if val is not None and val > 0:
                months[month_num] = val

        rows.append({
            "activo_raw": activo_str,
            "status": status,
            "instrument_id": instrument_id,
            "instrument_name": instrument_name,
            "match_candidates": candidates,
            "months": months,
        })

    return {
        "year": year,
        "rows": rows,
        "detected_months": sorted(col_month.values()),
        "warnings": warnings,
    }


@router.post("/import/confirm")
def confirm_forecast_import(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Apply a previously previewed forecast import.
    payload: {year, rows: [{instrument_id, months: {1: amount, ...}}], overwrite: bool}
    'overwrite' = True replaces existing values; False = skip if already set.
    """
    year = int(payload.get("year", 0))
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=422, detail="Año inválido")

    rows = payload.get("rows", [])
    overwrite = bool(payload.get("overwrite", True))

    upserted = 0
    skipped = 0

    for row in rows:
        inst_id = row.get("instrument_id")
        if not inst_id:
            skipped += 1
            continue
        months = row.get("months", {})
        for month_str, amount in months.items():
            month = int(month_str)
            if month < 1 or month > 12:
                continue
            if amount is None or amount == 0:
                continue
            existing = (
                db.query(ProventoForecast)
                .filter_by(instrument_id=inst_id, year=year, month=month)
                .first()
            )
            if existing:
                if overwrite:
                    existing.amount = float(amount)
                    upserted += 1
                else:
                    skipped += 1
            else:
                db.add(ProventoForecast(instrument_id=inst_id, year=year, month=month, amount=float(amount)))
                upserted += 1

    db.commit()
    return {"ok": True, "upserted": upserted, "skipped": skipped}
