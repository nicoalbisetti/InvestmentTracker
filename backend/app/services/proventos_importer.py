"""
Proventos Import Service
Parses "Proventos Recebidos" sheet from XP/Santander monthly Excel reports.
"""
from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session
from app.models.instrument import Instrument
from app.models.provento_item import ProvéntoItem, ProventoImportBatch

# ─── In-memory token cache ────────────────────────────────────────────────────
_TOKEN_CACHE: Dict[str, dict] = {}
TOKEN_TTL_MINUTES = 30

SHEET_NAME = "Proventos Recebidos"

EVENT_TYPE_MAP = {
    "Rendimento": "dividendo",
    "Juros Sobre Capital Próprio": "jcp",
    "PAGAMENTO DE JUROS": "jcp",
    "PAGAMENTO DE PRÊMIO/RENDIMENTOS": "dividendo",
}

CUSTODIAN_MAP = {
    "XP INVESTIMENTOS CCTVM S/A": "XP",
    "BANCO SANTANDER (BRASIL) S.A.": "SANTANDER",
}

# Prefixes that indicate Format B (no extractable ticker)
FORMAT_B_PREFIXES = {"CRI", "CRA", "DEB", "CFF", "CCE", "CCB"}


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ParsedProvento:
    produto_raw: str
    ticker: Optional[str]
    nombre_busqueda: str           # keyword for name search if Format B
    tipo_evento_raw: str
    custodian: str
    fecha_pago: date
    cantidad: Optional[float]
    precio_unitario: Optional[float]
    amount_brl: float
    type: str                      # 'dividendo' | 'jcp'


@dataclass
class ParsedProventosReport:
    items: List[ParsedProvento]
    total_from_excel: Optional[float]
    total_calculated: float
    total_validated: bool
    warnings: List[str]


@dataclass
class ProventosDiffItem:
    index: int
    status: str  # NEW | DUPLICATE | CONFLICT | NO_MATCH | AMBIGUOUS_MATCH
    parsed: ParsedProvento
    instrument_id: Optional[int]
    instrument_name: Optional[str]
    instrument_ticker: Optional[str]
    existing_amount_brl: Optional[float]
    match_candidates: List[dict]
    warnings: List[str]


@dataclass
class ProventosDiffReport:
    items: List[ProventosDiffItem]
    parse_warnings: List[str]


@dataclass
class ImportResult:
    success: bool
    batch_id: str
    imported_new: int
    imported_overwritten: int
    skipped_duplicates: int
    skipped_no_match: int
    skipped_manual: int
    total_amount_imported: float
    warnings: List[str]


# ─── Cache helpers ────────────────────────────────────────────────────────────

def _purge_expired():
    now = datetime.utcnow()
    expired = [t for t, v in _TOKEN_CACHE.items() if v["expires"] < now]
    for t in expired:
        del _TOKEN_CACHE[t]


def store_preview(diff_report: ProventosDiffReport, period_label: str) -> Tuple[str, datetime]:
    _purge_expired()
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)
    _TOKEN_CACHE[token] = {
        "diff_report": diff_report,
        "period_label": period_label,
        "expires": expires,
    }
    return token, expires


def load_preview(token: str) -> Optional[dict]:
    _purge_expired()
    entry = _TOKEN_CACHE.get(token)
    if entry and entry["expires"] > datetime.utcnow():
        return entry
    return None


def update_diff_item_mapping(token: str, index: int, instrument_id: int, db: Session) -> bool:
    """Assign an instrument_id to a NO_MATCH or AMBIGUOUS_MATCH item in the cache."""
    entry = _TOKEN_CACHE.get(token)
    if not entry:
        return False
    for item in entry["diff_report"].items:
        if item.index == index:
            inst = db.query(Instrument).filter(Instrument.id == instrument_id).first()
            if inst:
                item.instrument_id = instrument_id
                item.instrument_name = inst.name
                item.instrument_ticker = inst.ticker
                item.status = "NEW"
            return True
    return False


# ─── Parsing helpers ──────────────────────────────────────────────────────────

def parse_br_number(val) -> Optional[float]:
    """Parse Brazilian-format number: '3.712,50' → 3712.50"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        import math
        if isinstance(val, float) and math.isnan(val):
            return None
        return float(val)
    if isinstance(val, str):
        cleaned = val.strip().replace('.', '').replace(',', '.')
        if not cleaned or cleaned in ('-', 'nan', 'None'):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _normalize_custodian(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        return "XP"
    raw = raw.strip()
    for key, val in CUSTODIAN_MAP.items():
        if key in raw:
            return val
    raw_upper = raw.upper()
    if "INTER" in raw_upper:
        return "INTER"
    if "SANTANDER" in raw_upper:
        return "SANTANDER"
    return raw[:20] if raw else "XP"


def _extract_ticker_and_keyword(produto: str) -> Tuple[Optional[str], str]:
    """
    Returns (ticker, keyword_for_search).
    Format A: "MCRE11 - MAUÁ CAPITAL REAL ESTATE FDO..."  → ticker="MCRE11", keyword="MCRE11"
    Format B: "CRI - OPEA SECURITIZADORA S/A"            → ticker=None, keyword="OPEA"
    """
    parts = produto.split(" - ", 1)
    if len(parts) < 2:
        return None, produto.strip()

    prefix = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ""

    # Format B: known type prefix
    if prefix.upper() in FORMAT_B_PREFIXES:
        # Extract keyword: first meaningful word from the issuer name
        words = [w for w in rest.split() if len(w) >= 3 and w.upper() not in {"S/A", "S.A.", "S.A", "LTD", "LTDA"}]
        keyword = words[0] if words else rest.split()[0] if rest else produto
        return None, keyword

    # Format A: check ticker pattern (4-7 alphanumeric chars)
    if re.match(r'^[A-Z0-9]{4,7}$', prefix):
        return prefix, prefix

    return None, prefix


# ─── Main functions ───────────────────────────────────────────────────────────

def parse_excel(file_bytes: bytes) -> ParsedProventosReport:
    """Parse the 'Proventos Recebidos' sheet and return structured data."""
    warnings = []

    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo Excel: {e}")

    if SHEET_NAME not in xl.sheet_names:
        raise ValueError(
            f"Hoja '{SHEET_NAME}' no encontrada. Hojas disponibles: {xl.sheet_names}"
        )

    # Read with header=None so we control it
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=SHEET_NAME, header=None)
    if df.empty:
        raise ValueError("La hoja 'Proventos Recebidos' está vacía")

    # Row 0 is headers, data from row 1
    # Col indices: 0=Produto, 1=Pagamento, 2=Tipo de Evento, 3=Instituição, 4=Quantidade, 5=Preço unitário, 6=Valor líquido
    data_rows = df.iloc[1:]

    items: List[ParsedProvento] = []
    total_from_excel: Optional[float] = None

    for _, row in data_rows.iterrows():
        produto = row.iloc[0] if len(row) > 0 else None
        valor_liquido = row.iloc[6] if len(row) > 6 else None

        # Skip rows where Produto is NaN
        if pd.isna(produto) or str(produto).strip() == "":
            continue

        produto_str = str(produto).strip()

        # Skip "Total" row
        col5 = row.iloc[5] if len(row) > 5 else None
        if isinstance(col5, str) and col5.strip().lower() == "total":
            total_from_excel = parse_br_number(valor_liquido)
            continue
        # Also skip if produto itself is "Total"
        if produto_str.lower() in ("total", "subtotal"):
            total_from_excel = parse_br_number(valor_liquido)
            continue

        # Parse fields
        pagamento = row.iloc[1] if len(row) > 1 else None
        tipo_evento = row.iloc[2] if len(row) > 2 else None
        instituicao = row.iloc[3] if len(row) > 3 else None
        quantidade = row.iloc[4] if len(row) > 4 else None
        preco_unit = row.iloc[5] if len(row) > 5 else None

        # Parse date
        if pd.isna(pagamento):
            warnings.append(f"Fila sin fecha de pago ignorada: '{produto_str}'")
            continue

        try:
            if isinstance(pagamento, (datetime, pd.Timestamp)):
                fecha = pagamento.date() if hasattr(pagamento, 'date') else pagamento
            elif isinstance(pagamento, str):
                fecha = datetime.strptime(pagamento.strip(), "%d/%m/%Y").date()
            else:
                # Try pandas
                fecha = pd.to_datetime(pagamento).date()
        except Exception:
            warnings.append(f"Fecha inválida '{pagamento}' para '{produto_str}' — ignorando fila")
            continue

        # Parse amounts
        amount_brl = parse_br_number(valor_liquido)
        if amount_brl is None:
            warnings.append(f"Valor líquido inválido para '{produto_str}' — ignorando fila")
            continue

        cantidad = parse_br_number(quantidade)
        precio_unitario = parse_br_number(preco_unit)

        # Map event type
        tipo_str = str(tipo_evento).strip() if not pd.isna(tipo_evento) else ""
        prov_type = EVENT_TYPE_MAP.get(tipo_str)
        if prov_type is None:
            prov_type = "dividendo"
            if tipo_str:
                warnings.append(f"Tipo de Evento desconocido: '{tipo_str}' — clasificado como dividendo")

        # Normalize custodian
        inst_str = str(instituicao).strip() if not pd.isna(instituicao) else ""
        custodian = _normalize_custodian(inst_str)

        # Extract ticker / keyword
        ticker, keyword = _extract_ticker_and_keyword(produto_str)

        items.append(ParsedProvento(
            produto_raw=produto_str,
            ticker=ticker,
            nombre_busqueda=keyword,
            tipo_evento_raw=tipo_str,
            custodian=custodian,
            fecha_pago=fecha,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            amount_brl=amount_brl,
            type=prov_type,
        ))

    total_calculated = round(sum(i.amount_brl for i in items), 2)
    total_validated = total_from_excel is not None and abs(total_calculated - total_from_excel) <= 0.10

    if total_from_excel is not None and not total_validated:
        warnings.append(
            f"Suma calculada ({total_calculated:.2f}) no coincide con total del Excel ({total_from_excel:.2f})"
        )

    return ParsedProventosReport(
        items=items,
        total_from_excel=total_from_excel,
        total_calculated=total_calculated,
        total_validated=total_validated,
        warnings=warnings,
    )


def compute_diff(parsed: ParsedProventosReport, db: Session) -> ProventosDiffReport:
    """Match parsed proventos against DB instruments and existing proventos."""
    diff_items: List[ProventosDiffItem] = []
    seen_in_file: set = set()  # (instrument_id, date, type) already seen in this file

    for idx, p in enumerate(parsed.items):
        instrument_id = None
        instrument_name = None
        instrument_ticker = None
        match_candidates = []
        item_warnings = []
        status = "NEW"
        existing_amount_brl = None

        # --- Step 1: Instrument matching ---
        if p.ticker:
            # Format A: exact ticker match
            inst = db.query(Instrument).filter(Instrument.ticker == p.ticker).first()
            if inst:
                instrument_id = inst.id
                instrument_name = inst.name
                instrument_ticker = inst.ticker
            else:
                # No exact ticker match → try name search as fallback
                candidates = db.query(Instrument).filter(
                    Instrument.name.ilike(f"%{p.ticker}%")
                ).all()
                if len(candidates) == 1:
                    instrument_id = candidates[0].id
                    instrument_name = candidates[0].name
                    instrument_ticker = candidates[0].ticker
                elif len(candidates) > 1:
                    status = "AMBIGUOUS_MATCH"
                    match_candidates = [{"id": c.id, "name": c.name, "ticker": c.ticker} for c in candidates]
                else:
                    status = "NO_MATCH"
        else:
            # Format B: keyword search
            keyword = p.nombre_busqueda
            candidates = db.query(Instrument).filter(
                Instrument.name.ilike(f"%{keyword}%")
            ).all()
            if len(candidates) == 1:
                instrument_id = candidates[0].id
                instrument_name = candidates[0].name
                instrument_ticker = candidates[0].ticker
            elif len(candidates) > 1:
                status = "AMBIGUOUS_MATCH"
                match_candidates = [{"id": c.id, "name": c.name, "ticker": c.ticker} for c in candidates]
            else:
                status = "NO_MATCH"

        # --- Step 2: Duplicate within file (exact match: same instrument/date/type/amount) ---
        amount_key = round(p.amount_brl, 2)
        file_key = (instrument_id, p.fecha_pago, p.type, amount_key) if instrument_id else None
        if file_key and status == "NEW":
            if file_key in seen_in_file:
                status = "DUPLICATE"
                item_warnings.append("Fila duplicada exacta dentro del archivo")
            else:
                seen_in_file.add(file_key)

        # --- Step 3: Duplicate/Conflict check against DB ---
        if instrument_id and status == "NEW":
            existing = (
                db.query(ProvéntoItem)
                .filter(
                    ProvéntoItem.instrument_id == instrument_id,
                    ProvéntoItem.date == p.fecha_pago,
                    ProvéntoItem.type == p.type,
                )
                .all()
            )
            exact_match = next((e for e in existing if abs(e.amount_brl - p.amount_brl) <= 0.01), None)
            if exact_match:
                status = "DUPLICATE"
                existing_amount_brl = exact_match.amount_brl

        diff_items.append(ProventosDiffItem(
            index=idx,
            status=status,
            parsed=p,
            instrument_id=instrument_id,
            instrument_name=instrument_name,
            instrument_ticker=instrument_ticker,
            existing_amount_brl=existing_amount_brl,
            match_candidates=match_candidates,
            warnings=item_warnings,
        ))

    return ProventosDiffReport(items=diff_items, parse_warnings=parsed.warnings)


def apply_import(
    diff_report: ProventosDiffReport,
    force_duplicates: bool,
    skip_indices: List[int],
    manual_mappings: List[dict],  # [{index, instrument_id}]
    period_label: str,
    source_file: str,
    db: Session,
) -> ImportResult:
    """Apply confirmed import, creating ProvéntoItem records and an audit batch."""
    batch_id = str(uuid.uuid4())
    now_str = datetime.utcnow().isoformat()

    # Apply manual mappings first
    mapping_by_index = {m["index"]: m["instrument_id"] for m in manual_mappings}
    for item in diff_report.items:
        if item.index in mapping_by_index:
            new_inst_id = mapping_by_index[item.index]
            inst = db.query(Instrument).filter(Instrument.id == new_inst_id).first()
            if inst:
                item.instrument_id = inst.id
                item.instrument_name = inst.name
                item.instrument_ticker = inst.ticker
                if item.status in ("NO_MATCH", "AMBIGUOUS_MATCH"):
                    # Re-check for duplicate
                    existing = (
                        db.query(ProvéntoItem)
                        .filter_by(instrument_id=inst.id, date=item.parsed.fecha_pago, type=item.parsed.type)
                        .first()
                    )
                    if existing:
                        if abs(existing.amount_brl - item.parsed.amount_brl) <= 0.01:
                            item.status = "DUPLICATE"
                            item.existing_amount_brl = existing.amount_brl
                        else:
                            item.status = "CONFLICT"
                            item.existing_amount_brl = existing.amount_brl
                    else:
                        item.status = "NEW"

    imported_new = 0
    imported_overwritten = 0
    skipped_duplicates = 0
    skipped_no_match = 0
    skipped_manual = 0
    total_amount_imported = 0.0
    result_warnings = []

    for item in diff_report.items:
        p = item.parsed

        if item.index in skip_indices:
            skipped_manual += 1
            continue

        if item.status in ("NO_MATCH", "AMBIGUOUS_MATCH"):
            skipped_no_match += 1
            continue

        if item.status == "DUPLICATE":
            if not force_duplicates:
                skipped_duplicates += 1
                continue
            # Overwrite
            existing = (
                db.query(ProvéntoItem)
                .filter_by(instrument_id=item.instrument_id, date=p.fecha_pago, type=p.type)
                .first()
            )
            if existing:
                existing.amount_brl = p.amount_brl
                existing.quantity = p.cantidad
                existing.unit_price = p.precio_unitario
                existing.custodian = p.custodian
                existing.source = "EXCEL_XP_SANTANDER"
                existing.import_batch_id = batch_id
                existing.raw_event_type = p.tipo_evento_raw
                imported_overwritten += 1
                total_amount_imported += p.amount_brl
            continue

        if item.status == "CONFLICT":
            if not force_duplicates:
                skipped_duplicates += 1
                continue
            existing = (
                db.query(ProvéntoItem)
                .filter_by(instrument_id=item.instrument_id, date=p.fecha_pago, type=p.type)
                .first()
            )
            if existing:
                existing.amount_brl = p.amount_brl
                existing.quantity = p.cantidad
                existing.unit_price = p.precio_unitario
                existing.custodian = p.custodian
                existing.source = "EXCEL_XP_SANTANDER"
                existing.import_batch_id = batch_id
                existing.raw_event_type = p.tipo_evento_raw
                imported_overwritten += 1
                total_amount_imported += p.amount_brl
            continue

        # NEW
        if item.status == "NEW" and item.instrument_id:
            db.add(ProvéntoItem(
                instrument_id=item.instrument_id,
                date=p.fecha_pago,
                amount_brl=p.amount_brl,
                type=p.type,
                quantity=p.cantidad,
                unit_price=p.precio_unitario,
                custodian=p.custodian,
                source="EXCEL_XP_SANTANDER",
                import_batch_id=batch_id,
                raw_event_type=p.tipo_evento_raw,
            ))
            imported_new += 1
            total_amount_imported += p.amount_brl

    # Create audit batch record
    db.add(ProventoImportBatch(
        id=batch_id,
        imported_at=now_str,
        period_label=period_label,
        source_file=source_file,
        total_amount=round(total_amount_imported, 2),
        record_count=imported_new + imported_overwritten,
    ))

    db.commit()

    return ImportResult(
        success=True,
        batch_id=batch_id,
        imported_new=imported_new,
        imported_overwritten=imported_overwritten,
        skipped_duplicates=skipped_duplicates,
        skipped_no_match=skipped_no_match,
        skipped_manual=skipped_manual,
        total_amount_imported=round(total_amount_imported, 2),
        warnings=result_warnings,
    )
