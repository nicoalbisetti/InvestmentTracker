"""
Fixed Income Import Service
Parses XP/Santander monthly Excel reports and computes/applies diffs to the DB.
"""
from __future__ import annotations

import io
import math
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from app.models.instrument_code_mapping import InstrumentCodeMapping
from app.schemas.fixed_income_import import (
    ImportConfig, ParsedInstrument, DiffItem, ImportResult,
)

# ─── In-memory token cache ────────────────────────────────────────────────────
# {token: {"config": ImportConfig, "diff": list[DiffItem], "parsed": list[ParsedInstrument],
#          "expires": datetime}}
_TOKEN_CACHE: Dict[str, dict] = {}
TOKEN_TTL_MINUTES = 30


def _purge_expired():
    now = datetime.utcnow()
    expired = [t for t, v in _TOKEN_CACHE.items() if v["expires"] < now]
    for t in expired:
        del _TOKEN_CACHE[t]


def store_preview(config: ImportConfig, diff: List[DiffItem], parsed: List[ParsedInstrument]) -> Tuple[str, datetime]:
    _purge_expired()
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)
    _TOKEN_CACHE[token] = {"config": config, "diff": diff, "parsed": parsed, "expires": expires}
    return token, expires


def load_preview(token: str) -> Optional[dict]:
    _purge_expired()
    entry = _TOKEN_CACHE.get(token)
    if entry and entry["expires"] > datetime.utcnow():
        return entry
    return None


def update_diff_item(token: str, codigo: str, custodian_override: Optional[str], instrument_id: int) -> bool:
    """Map an Excel codigo to an existing instrument_id inside the token cache."""
    entry = _TOKEN_CACHE.get(token)
    if not entry:
        return False
    for item in entry["diff"]:
        if item.codigo == codigo and item.custodian_override == custodian_override:
            item.instrument_id = instrument_id
            item.status = "UPDATED"
    return True


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val):
            return None
        return float(val)
    s = str(val).strip()
    if not s or s in ("-", "nan", "None", "#N/A", "#VALUE!"):
        return None
    try:
        # Handle Brazilian locale: "1.234,56" → 1234.56
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s or s in ("-", "nan", "None"):
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _normalize_custodian(raw: str) -> str:
    if not raw or str(raw).strip() in ("-", "nan", "None"):
        return "DESCONHECIDO"
    raw = str(raw).strip().upper()
    if "XP" in raw:
        return "XP"
    if "SANTANDER" in raw:
        return "SANTANDER"
    if "INTER" in raw:
        return "INTER"
    if "BRADESCO" in raw:
        return "BRADESCO"
    if "ITAU" in raw or "ITAÚ" in raw:
        return "ITAU"
    return raw[:20]


def _extract_asset_class(produto: str) -> str:
    """Extract asset_class from the Produto name prefix."""
    p = str(produto).strip().upper()
    for prefix, cls in [
        ("CDB ", "CDB"), ("CDB-", "CDB"),
        ("CRA ", "CRA"), ("CRA-", "CRA"),
        ("CRI ", "CRI"), ("CRI-", "CRI"),
        ("DEB ", "DEB"), ("DEB-", "DEB"),
        ("LCA ", "LCA"), ("LCA-", "LCA"),
        ("LCI ", "LCI"), ("LCI-", "LCI"),
        ("LIG ", "LIG"), ("LIG-", "LIG"),
        ("CFF ", "FUNDO_CREDITO"), ("CFF-", "FUNDO_CREDITO"),
        ("TESOURO SELIC", "TD"), ("TESOURO IPCA", "TD"),
        ("TESOURO PREFIXADO", "TD"), ("TESOURO ", "TD"),
    ]:
        if p.startswith(prefix):
            return cls
    return "OUTRO"


def _extract_tipo(produto: str) -> str:
    """Extract tipo (used as sub-type label) from Produto name."""
    p = str(produto).strip().upper()
    for prefix in ["CDB", "CRA", "CRI", "DEB", "LCA", "LCI", "LIG", "CFF"]:
        if p.startswith(prefix):
            return prefix
    if p.startswith("TESOURO"):
        return "TD"
    return "OUTRO"


def _clean_nome(produto: str) -> Tuple[str, bool]:
    """Return (cleaned name, in_liquidation flag)."""
    s = str(produto).strip()
    in_liq = False
    for marker in [
        " - EM LIQUIDACAO EXTRAJUDICIAL",
        " - EM LIQUIDAÇÃO EXTRAJUDICIAL",
        " EM LIQUIDACAO EXTRAJUDICIAL",
        " EM LIQUIDAÇÃO EXTRAJUDICIAL",
        "- EM LIQUIDACAO EXTRAJUDICIAL",
    ]:
        if marker.upper() in s.upper():
            s = s.upper().replace(marker.upper(), "").strip()
            in_liq = True
    return s, in_liq


# ─── Auto-match scoring ───────────────────────────────────────────────────────

_PT_MONTHS = {
    1: 'JAN', 2: 'FEV', 3: 'MAR', 4: 'ABR', 5: 'MAI', 6: 'JUN',
    7: 'JUL', 8: 'AGO', 9: 'SET', 10: 'OUT', 11: 'NOV', 12: 'DEZ',
}
_STOPWORDS = {
    'BANCO', 'SA', 'S/A', 'S.A', 'DE', 'DO', 'DA', 'DOS', 'DAS', 'EM', 'NO',
    'COMPANHIA', 'FINANCEIRA', 'INVESTIMENTOS', 'BRASIL', 'SECURITIZADORA',
    'DISTRIBUIDORA', 'RENDA', 'FIXA', 'CDB', 'CRI', 'CRA', 'DEB', 'LCA',
    'LCI', 'LIG', 'CFF', 'TESOURO', 'DIRETO', 'NACIONAL', 'LTDA', 'MULTIPLO',
    'CORRETORA', 'LIQUIDACAO', 'EXTRAJUDICIAL', 'FORTE', 'BRASILEIRO',
}


def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful bank/entity keywords from a product or emissor name."""
    words = re.split(r'[\s\-\/\.\(\)]+', text.upper())
    # len >= 3 to capture short names like BMG, ETB, XPS, C6 is 2 (handled separately)
    return list(dict.fromkeys(  # deduplicate preserving order
        w for w in words if len(w) >= 3 and w not in _STOPWORDS and not w.isdigit()
    ))


def auto_match_score(parsed: ParsedInstrument, inst: Instrument) -> int:
    """
    Score how likely `inst` (from DB) matches `parsed` (from Excel).
    Higher = better match. Returns 0 if no meaningful match.
    """
    score = 0
    name_upper = inst.name.upper()

    # 1. Asset type prefix at start of DB name
    has_prefix = name_upper.startswith(parsed.tipo)
    if has_prefix:
        score += 3

    # 2. Bank/entity keywords from produto or emissor appear in DB name
    keywords = _extract_keywords(parsed.produto)
    if parsed.emissor:
        keywords += _extract_keywords(parsed.emissor)
    matched_kw = False
    for kw in keywords:
        if kw in name_upper:
            score += 3
            matched_kw = True
            break  # count only once

    # 3. Custodian match
    if inst.custodian and parsed.custodian and inst.custodian == parsed.custodian:
        score += 1

    # 4. Maturity month+year in DB name (e.g. "Mar 2027" or "MAR 2027")
    has_maturity = False
    if parsed.vencimento:
        m = _PT_MONTHS.get(parsed.vencimento.month, '')
        y = str(parsed.vencimento.year)
        if m and (f"{m} {y}" in name_upper or f"{m}. {y}" in name_upper):
            score += 3
            has_maturity = True

    # Require: keyword match OR (prefix + maturity) — avoids spurious matches
    if not matched_kw and not (has_prefix and has_maturity):
        return 0

    return score


def find_best_auto_match(
    parsed: ParsedInstrument,
    candidates: List[Instrument],
    threshold: int = 5,
) -> Optional[Tuple[Instrument, int]]:
    """Return (best_matching_instrument, score) or None if below threshold."""
    best: Optional[Tuple[Instrument, int]] = None
    for inst in candidates:
        s = auto_match_score(parsed, inst)
        if s >= threshold and (best is None or s > best[1]):
            best = (inst, s)
    return best


# ─── Parser ───────────────────────────────────────────────────────────────────

def parse_excel(file_bytes: bytes, config: ImportConfig) -> Tuple[List[ParsedInstrument], List[str]]:
    """
    Parse the monthly XP/Santander Excel report.
    Returns (list of ParsedInstrument, list of global warnings).
    """
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    warnings: List[str] = []
    parsed: List[ParsedInstrument] = []

    sheet_names = xls.sheet_names

    # ── Renda Fixa sheet ─────────────────────────────────────────────────────
    rf_sheet = next((s for s in sheet_names if "Renda Fixa" in s), None)
    if rf_sheet:
        df = pd.read_excel(xls, sheet_name=rf_sheet, header=None)
        # Row 0 = headers, rows 1+ = data
        data = df.iloc[1:].reset_index(drop=True)
        # Filter rows where col 0 (Produto) is NaN/empty
        data = data[data.iloc[:, 0].notna()]
        data = data[data.iloc[:, 0].astype(str).str.strip().ne("")]

        # Track codes to detect duplicates across custodians
        code_custodians: Dict[str, List[str]] = {}

        rows_rf: List[ParsedInstrument] = []
        for _, row in data.iterrows():
            produto_raw = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if not produto_raw or produto_raw.lower() in ("nan", "produto", "total"):
                continue

            nome, in_liq = _clean_nome(produto_raw)
            asset_class = _extract_asset_class(produto_raw)
            tipo = _extract_tipo(produto_raw)

            # col 1: Instituição → custodian
            custodian_raw = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
            custodian = _normalize_custodian(custodian_raw)

            # col 2: Emissor
            emissor = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ""

            # col 3: Código (ticker)
            codigo_raw = row.iloc[3] if len(row) > 3 else None
            codigo = str(codigo_raw).strip() if pd.notna(codigo_raw) else ""
            if not codigo or codigo.lower() == "nan":
                # Use name as fallback key
                codigo = nome[:40]

            # col 4: Indexador
            idx_raw = row.iloc[4] if len(row) > 4 else None
            indexador_str = str(idx_raw).strip() if pd.notna(idx_raw) else None
            indexador = None if not indexador_str or indexador_str in ("-", "nan", "") else indexador_str

            # col 6: Data de Emissão
            emissao_raw = row.iloc[6] if len(row) > 6 else None
            emissao = _parse_date(emissao_raw)

            # col 7: Vencimento
            venc_raw = row.iloc[7] if len(row) > 7 else None
            vencimento = _parse_date(venc_raw)

            # col 9: Quantidade Disponível (prefer over col 8)
            qtd_raw = row.iloc[9] if len(row) > 9 else (row.iloc[8] if len(row) > 8 else None)
            quantidade = _safe_float(qtd_raw)

            # cols 13/14: MTM price/value; cols 15/16: CURVA price/value
            price_mtm = _safe_float(row.iloc[13]) if len(row) > 13 else None
            valor_mtm = _safe_float(row.iloc[14]) if len(row) > 14 else None
            price_curva = _safe_float(row.iloc[15]) if len(row) > 15 else None
            valor_curva = _safe_float(row.iloc[16]) if len(row) > 16 else None

            # Resolve balance_brl: MTM preferred over CURVA
            if valor_mtm is not None:
                valor_brl = valor_mtm
                unit_price = price_mtm
            elif valor_curva is not None:
                valor_brl = valor_curva
                unit_price = price_curva
            else:
                valor_brl = None
                unit_price = None

            # Apply custodian filter
            if config.custodian_filter and custodian != config.custodian_filter:
                continue

            # Track for duplicate detection
            if codigo not in code_custodians:
                code_custodians[codigo] = []
            code_custodians[codigo].append(custodian)

            # Warnings
            item_warnings: List[str] = []
            if in_liq:
                item_warnings.append("Em liquidação extrajudicial")
            if valor_brl is None:
                item_warnings.append("Sin precio disponible (ANBIMA no valoriza)")
            if vencimento and vencimento.year > 2060:
                item_warnings.append(f"Vencimento inusual (año {vencimento.year})")

            rows_rf.append(ParsedInstrument(
                produto=produto_raw,
                codigo=codigo,
                tipo=tipo,
                emissor=emissor,
                custodian=custodian,
                custodian_override=None,  # set below after duplicate detection
                indexador=indexador,
                emissao=emissao,
                vencimento=vencimento,
                quantidade=quantidade,
                valor_brl=valor_brl,
                unit_price=unit_price,
                valor_mtm=valor_mtm,
                valor_curva=valor_curva,
                capital_invested=None,
                in_liquidation=in_liq,
            ))

        # Set custodian_override for duplicate codes
        for item in rows_rf:
            custodians_for_code = code_custodians.get(item.codigo, [])
            if len(custodians_for_code) > 1:
                item.custodian_override = item.custodian
                warnings.append(
                    f"{item.codigo}: aparece en {len(custodians_for_code)} custodios "
                    f"({', '.join(set(custodians_for_code))}) — se importarán como posiciones separadas"
                )

        parsed.extend(rows_rf)
    else:
        warnings.append("Hoja 'Posição - Renda Fixa' no encontrada en el archivo")

    # ── Tesouro Direto sheet ─────────────────────────────────────────────────
    td_sheet = next((s for s in sheet_names if "Tesouro Direto" in s), None)
    if td_sheet:
        df_td = pd.read_excel(xls, sheet_name=td_sheet, header=None)
        data_td = df_td.iloc[1:].reset_index(drop=True)
        data_td = data_td[data_td.iloc[:, 0].notna()]
        data_td = data_td[data_td.iloc[:, 0].astype(str).str.strip().ne("")]

        for _, row in data_td.iterrows():
            produto_raw = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if not produto_raw or produto_raw.lower() in ("nan", "produto"):
                continue

            nome = produto_raw
            asset_class = "TD"

            # col 1: Instituição
            custodian_raw = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
            custodian = _normalize_custodian(custodian_raw)

            # col 2: Código ISIN
            codigo_raw = row.iloc[2] if len(row) > 2 else None
            codigo = str(codigo_raw).strip() if pd.notna(codigo_raw) else nome[:40]
            if not codigo or codigo.lower() == "nan":
                codigo = nome[:40]

            # col 3: Indexador
            idx_raw = row.iloc[3] if len(row) > 3 else None
            indexador_str = str(idx_raw).strip() if pd.notna(idx_raw) else None
            indexador = None if not indexador_str or indexador_str in ("-", "nan", "") else indexador_str

            # col 4: Vencimento
            venc_raw = row.iloc[4] if len(row) > 4 else None
            vencimento = _parse_date(venc_raw)

            # col 5: Quantidade
            qtd_raw = row.iloc[5] if len(row) > 5 else None
            quantidade = _safe_float(qtd_raw)

            # col 9: Valor Aplicado (capital)
            capital_raw = row.iloc[9] if len(row) > 9 else None
            capital_invested = _safe_float(capital_raw)

            # col 12: Valor Atualizado → balance_brl
            valor_raw = row.iloc[12] if len(row) > 12 else None
            valor_brl = _safe_float(valor_raw)

            # Apply custodian filter
            if config.custodian_filter and custodian != config.custodian_filter:
                continue

            parsed.append(ParsedInstrument(
                produto=produto_raw,
                codigo=codigo,
                tipo="TD",
                emissor="Tesouro Nacional",
                custodian=custodian,
                custodian_override=None,
                indexador=indexador,
                emissao=None,
                vencimento=vencimento,
                quantidade=quantidade,
                valor_brl=valor_brl,
                unit_price=None,
                valor_mtm=None,
                valor_curva=None,
                capital_invested=capital_invested,
                in_liquidation=False,
            ))

    return parsed, warnings


# ─── Diff Computation ─────────────────────────────────────────────────────────

def _find_instrument(parsed: ParsedInstrument, db: Session) -> Optional[Instrument]:
    """Look up instrument by ticker, then by code mapping, then by name."""
    # 1. By ticker
    if parsed.codigo:
        inst = db.query(Instrument).filter(Instrument.ticker == parsed.codigo).first()
        if inst:
            return inst
        # Check custom mapping table
        mapping = db.query(InstrumentCodeMapping).filter(
            InstrumentCodeMapping.codigo_excel == parsed.codigo
        ).first()
        if mapping:
            return db.query(Instrument).filter(Instrument.id == mapping.instrument_id).first()
    # 2. By name (exact match on existing instruments)
    return db.query(Instrument).filter(
        Instrument.name == parsed.produto,
        Instrument.type == "renta_fija",
    ).first()


def _get_previous_position(instrument_id: int, custodian_override: Optional[str],
                            period_date: date, db: Session) -> Optional[MonthlyPosition]:
    """Get the most recent MonthlyPosition for (instrument, custodian_override) before period_date."""
    q = db.query(MonthlyPosition).filter(
        MonthlyPosition.instrument_id == instrument_id,
        MonthlyPosition.date < period_date,
    )
    if custodian_override is not None:
        q = q.filter(MonthlyPosition.custodian_override == custodian_override)
    else:
        q = q.filter(MonthlyPosition.custodian_override.is_(None))
    return q.order_by(MonthlyPosition.date.desc()).first()


def compute_diff(
    parsed: List[ParsedInstrument],
    period_date: date,
    config: ImportConfig,
    db: Session,
) -> List[DiffItem]:
    """Compare parsed instruments against DB and produce a list of DiffItems."""
    diff: List[DiffItem] = []
    seen_instrument_ids: set = set()

    # Pre-load ALL renta_fija instruments for auto-matching (include cerrado/sin_datos —
    # they may still be the correct match for a newly-appearing Excel instrument)
    rf_candidates = db.query(Instrument).filter(
        Instrument.type == "renta_fija",
    ).all()

    for p in parsed:
        inst = _find_instrument(p, db)
        item_warnings = list(p.in_liquidation and ["Em liquidación extrajudicial"] or [])
        if p.valor_brl is None:
            item_warnings.append("Sin precio disponible")
        if p.vencimento and p.vencimento.year > 2060:
            item_warnings.append(f"Vencimento inusual (año {p.vencimento.year})")

        auto_matched = False
        if inst is None:
            # Auto-match: score >= 9 = high confidence (auto-confirm as UPDATED)
            #             score 5-8 = medium confidence (stays NEW, shown as suggestion in modal)
            match = find_best_auto_match(p, rf_candidates, threshold=9)
            if match:
                inst = match[0]
                auto_matched = True
                item_warnings.insert(0, f"Auto-match a '{inst.name}' (score {match[1]}) — verificar antes de importar")

        if inst is None:
            # NEW instrument
            diff.append(DiffItem(
                status="NEW",
                codigo=p.codigo,
                nome=p.produto,
                tipo=p.tipo,
                emissor=p.emissor,
                custodian=p.custodian,
                custodian_override=p.custodian_override,
                indexador=p.indexador,
                emissao=p.emissao,
                vencimento=p.vencimento,
                in_liquidation=p.in_liquidation,
                valor_actual_brl=p.valor_brl if config.import_values else None,
                valor_anterior_brl=None,
                variacion_brl=None,
                variacion_pct=None,
                cantidad_actual=p.quantidade if config.import_quantities else None,
                cantidad_anterior=None,
                unit_price=p.unit_price if config.import_unit_price else None,
                capital_invested=p.capital_invested,
                instrument_id=None,
                warnings=item_warnings,
            ))
        else:
            seen_instrument_ids.add(inst.id)
            prev_pos = _get_previous_position(inst.id, p.custodian_override, period_date, db)
            # Also check if there's already a position for this exact period
            period_pos_q = db.query(MonthlyPosition).filter(
                MonthlyPosition.instrument_id == inst.id,
                MonthlyPosition.date == period_date,
            )
            if p.custodian_override is not None:
                period_pos_q = period_pos_q.filter(
                    MonthlyPosition.custodian_override == p.custodian_override
                )
            else:
                period_pos_q = period_pos_q.filter(
                    MonthlyPosition.custodian_override.is_(None)
                )
            period_pos = period_pos_q.first()

            valor_anterior = period_pos.balance_brl if period_pos else (prev_pos.balance_brl if prev_pos else None)
            cantidad_anterior = period_pos.quantity if period_pos else (prev_pos.quantity if prev_pos else None)

            # Determine if there are differences
            has_diff = False
            variacion_brl = None
            variacion_pct = None

            if config.import_values and p.valor_brl is not None:
                if valor_anterior is None or abs((p.valor_brl or 0) - (valor_anterior or 0)) > 0.01:
                    threshold = config.value_change_threshold_pct
                    if threshold and valor_anterior:
                        change_pct = abs(p.valor_brl - valor_anterior) / valor_anterior * 100
                        if change_pct >= threshold:
                            has_diff = True
                    else:
                        has_diff = True
                if valor_anterior is not None:
                    variacion_brl = (p.valor_brl or 0) - valor_anterior
                    variacion_pct = (variacion_brl / valor_anterior * 100) if valor_anterior else None

            if config.import_quantities and p.quantidade is not None:
                if cantidad_anterior is None or abs((p.quantidade or 0) - (cantidad_anterior or 0)) > 0.001:
                    has_diff = True

            if config.import_instrument_data:
                if config.import_maturity_date and p.vencimento and p.vencimento != inst.maturity_date:
                    has_diff = True
                if config.import_indexador and p.indexador and p.indexador != inst.index_type:
                    has_diff = True
                if config.import_issue_date and p.emissao and p.emissao != inst.issue_date:
                    has_diff = True

            status = "UPDATED" if has_diff else "UNCHANGED"

            diff.append(DiffItem(
                status=status,
                codigo=p.codigo,
                nome=p.produto,
                tipo=p.tipo,
                emissor=p.emissor,
                custodian=p.custodian,
                custodian_override=p.custodian_override,
                indexador=p.indexador,
                emissao=p.emissao,
                vencimento=p.vencimento,
                in_liquidation=p.in_liquidation,
                valor_actual_brl=p.valor_brl if config.import_values else None,
                valor_anterior_brl=valor_anterior if config.import_values else None,
                variacion_brl=variacion_brl if config.import_values else None,
                variacion_pct=variacion_pct if config.import_values else None,
                cantidad_actual=p.quantidade if config.import_quantities else None,
                cantidad_anterior=cantidad_anterior if config.import_quantities else None,
                unit_price=p.unit_price if config.import_unit_price else None,
                capital_invested=p.capital_invested,
                instrument_id=inst.id,
                warnings=item_warnings,
            ))

    # DISAPPEARED: active renta_fija instruments (same custodian filter) not in the Excel
    q_disappeared = db.query(Instrument).filter(
        Instrument.type == "renta_fija",
        Instrument.status == "activo",
    )
    if config.custodian_filter:
        q_disappeared = q_disappeared.filter(Instrument.custodian == config.custodian_filter)

    for inst in q_disappeared.all():
        if inst.id not in seen_instrument_ids:
            prev_pos = db.query(MonthlyPosition).filter(
                MonthlyPosition.instrument_id == inst.id,
            ).order_by(MonthlyPosition.date.desc()).first()
            diff.append(DiffItem(
                status="DISAPPEARED",
                codigo=inst.ticker or "",
                nome=inst.name,
                tipo=inst.asset_class or "renta_fija",
                emissor="",
                custodian=inst.custodian,
                custodian_override=None,
                indexador=inst.index_type,
                vencimento=inst.maturity_date,
                in_liquidation=inst.in_liquidation or False,
                ultimo_valor_brl=prev_pos.balance_brl if prev_pos else None,
                ultima_fecha=prev_pos.date if prev_pos else None,
                instrument_id=inst.id,
                warnings=[],
            ))

    return diff


# ─── Apply Import ─────────────────────────────────────────────────────────────

def _make_skip_key(codigo: str, custodian_override: Optional[str]) -> str:
    return f"{codigo}::{custodian_override or ''}"


def apply_import(
    diff: List[DiffItem],
    parsed: List[ParsedInstrument],
    period_date: date,
    config: ImportConfig,
    skip_keys: List[str],
    db: Session,
) -> ImportResult:
    """Apply the confirmed import to the database."""
    skip_set = set(skip_keys)
    created_instruments = 0
    new_positions = 0
    updated_positions = 0
    closed_instruments = 0
    skipped = 0
    warnings: List[str] = []
    errors: List[str] = []

    # Build a lookup from (codigo, custodian_override) → ParsedInstrument
    parsed_map: Dict[str, ParsedInstrument] = {}
    for p in parsed:
        key = _make_skip_key(p.codigo, p.custodian_override)
        parsed_map[key] = p

    for item in diff:
        skip_key = _make_skip_key(item.codigo, item.custodian_override)

        if skip_key in skip_set:
            skipped += 1
            continue

        if item.status == "DISAPPEARED":
            # User explicitly selected this item → close it
            if item.instrument_id is not None:
                try:
                    inst = db.query(Instrument).filter(Instrument.id == item.instrument_id).first()
                    if inst:
                        inst.status = "cerrado"
                        # Upsert zero-balance position for the current period
                        pos = db.query(MonthlyPosition).filter(
                            MonthlyPosition.instrument_id == inst.id,
                            MonthlyPosition.date == period_date,
                        ).first()
                        if pos:
                            pos.balance_brl = 0.0
                            if pos.balance_usd is not None:
                                pos.balance_usd = 0.0
                        else:
                            db.add(MonthlyPosition(
                                instrument_id=inst.id,
                                date=period_date,
                                balance_brl=0.0,
                            ))
                        closed_instruments += 1
                    else:
                        errors.append(f"{item.codigo}: instrumento ID {item.instrument_id} no encontrado")
                except Exception as e:
                    errors.append(f"{item.codigo}: {str(e)}")
                    db.rollback()
            else:
                skipped += 1
            continue

        if item.status == "UNCHANGED":
            # Only process UNCHANGED if explicitly selected (i.e., NOT in skip_set)
            # Since we're here (not skipped), it means user explicitly selected it
            pass

        p = parsed_map.get(skip_key)
        if p is None:
            skipped += 1
            continue

        try:
            if item.status == "NEW":
                if not config.create_new_instruments:
                    skipped += 1
                    continue

                inst = Instrument(
                    name=p.produto,
                    ticker=p.codigo if p.codigo else None,
                    type="renta_fija",
                    asset_class=p.tipo,
                    currency="BRL",
                    status="activo",
                    in_liquidation=p.in_liquidation,
                )
                if config.import_custodian:
                    inst.custodian = p.custodian
                else:
                    inst.custodian = p.custodian  # always set for DB integrity
                if config.import_maturity_date:
                    inst.maturity_date = p.vencimento
                if config.import_issue_date:
                    inst.issue_date = p.emissao
                if config.import_indexador:
                    inst.index_type = p.indexador
                db.add(inst)
                db.flush()
                created_instruments += 1
                item.instrument_id = inst.id

                if not config.create_base_only:
                    _upsert_position(inst.id, p, period_date, config, db)
                    new_positions += 1

            elif item.status in ("UPDATED", "UNCHANGED"):
                inst = db.query(Instrument).filter(Instrument.id == item.instrument_id).first()
                if inst is None:
                    errors.append(f"{item.codigo}: instrumento ID {item.instrument_id} no encontrado")
                    continue

                if config.import_instrument_data:
                    if config.import_maturity_date and p.vencimento:
                        inst.maturity_date = p.vencimento
                    if config.import_issue_date and p.emissao:
                        inst.issue_date = p.emissao
                    if config.import_indexador and p.indexador:
                        inst.index_type = p.indexador
                    if config.import_custodian and p.custodian:
                        inst.custodian = p.custodian
                    if config.import_name and p.produto:
                        inst.name = p.produto
                    if p.in_liquidation:
                        inst.in_liquidation = True
                    if not inst.ticker and p.codigo:
                        inst.ticker = p.codigo

                result = _upsert_position(inst.id, p, period_date, config, db)
                if result == "created":
                    new_positions += 1
                else:
                    updated_positions += 1

        except Exception as e:
            errors.append(f"{item.codigo}: {str(e)}")
            db.rollback()
            continue

    db.commit()

    return ImportResult(
        success=len(errors) == 0,
        imported={
            "new_instruments": created_instruments,
            "new_positions": new_positions,
            "updated_positions": updated_positions,
            "closed_instruments": closed_instruments,
        },
        skipped=skipped,
        warnings=warnings,
        errors=errors,
    )


def _upsert_position(
    instrument_id: int,
    p: ParsedInstrument,
    period_date: date,
    config: ImportConfig,
    db: Session,
) -> str:
    """Create or update MonthlyPosition for the given instrument and period."""
    q = db.query(MonthlyPosition).filter(
        MonthlyPosition.instrument_id == instrument_id,
        MonthlyPosition.date == period_date,
    )
    if p.custodian_override is not None:
        q = q.filter(MonthlyPosition.custodian_override == p.custodian_override)
    else:
        q = q.filter(MonthlyPosition.custodian_override.is_(None))

    pos = q.first()
    is_new = pos is None

    if is_new:
        prev = _get_previous_position(instrument_id, p.custodian_override, period_date, db)
        pos = MonthlyPosition(
            instrument_id=instrument_id,
            date=period_date,
            custodian_override=p.custodian_override,
            previous_balance=prev.balance_brl if prev else None,
        )
        db.add(pos)

    threshold = config.value_change_threshold_pct

    if config.import_values and p.valor_brl is not None:
        if threshold and pos.balance_brl is not None and pos.balance_brl != 0:
            change_pct = abs(p.valor_brl - pos.balance_brl) / abs(pos.balance_brl) * 100
            if change_pct >= threshold:
                pos.balance_brl = p.valor_brl
        else:
            pos.balance_brl = p.valor_brl

    if config.import_quantities and p.quantidade is not None:
        pos.quantity = p.quantidade

    if config.import_unit_price and p.unit_price is not None:
        pos.unit_price = p.unit_price

    if p.capital_invested is not None:
        pos.capital_invested = p.capital_invested

    return "created" if is_new else "updated"
