"""
International Import Service — XP International PDF Parser
Parses monthly PDF statements from XP International and applies diffs to the DB.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.instrument import Instrument
from app.models.instrument_code_mapping import InstrumentCodeMapping
from app.models.monthly_position import MonthlyPosition
from app.models.provento_item import ProvéntoItem

# ─── In-memory token cache ────────────────────────────────────────────────────
_TOKEN_CACHE: Dict[str, dict] = {}
TOKEN_TTL_MINUTES = 30

BOND_PATTERN = re.compile(r"(\d+\.?\d*)%,\s+(\d{2}/\d{2}/\d{4})")
UST_MARKER = "UNITED STATES TREASURY"


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ParsedPosition(BaseModel):
    descricao: str
    symbol: Optional[str] = None
    cusip: Optional[str] = None
    quantidade: float
    preco_usd: float
    posicao_usd: float
    posicao_anterior_usd: float
    pct_carteira: float


class ParsedDividend(BaseModel):
    pay_date: date
    rec_date: Optional[date] = None
    symbol: Optional[str] = None
    cusip: Optional[str] = None
    shares: float
    dividend_per_share: float
    valor_liquido_usd: float
    withholding_rate: float = 0.0


class ParsedReport(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    account_number: Optional[str] = None
    positions: List[ParsedPosition] = []
    dividends: List[ParsedDividend] = []
    total_portfolio_usd: float = 0.0
    available_cash_usd: float = 0.0
    parse_warnings: List[str] = []


class InstrumentClassification(BaseModel):
    asset_class: Literal["UST", "CORP_BOND", "ETF"]
    type: str               # "renta_fija" | "accion"
    currency: str = "USD"
    location: str = "exterior"
    custodian: str = "XP_INTERNATIONAL"
    issuer: str = ""
    coupon_rate: Optional[float] = None
    maturity_date: Optional[date] = None
    ticker_for_prices: Optional[str] = None


class MatchResult(BaseModel):
    status: Literal["EXACT", "MAPPED", "NEW"]
    instrument_id: Optional[int] = None
    match_key: str = ""


class InternationalImportConfig(BaseModel):
    usd_brl_rate: float
    create_new_instruments: bool = True
    import_unit_price: bool = True
    import_quantities: bool = True
    period_date: str  # "YYYY-MM-DD"


class InternationalDiffItem(BaseModel):
    descricao: str
    symbol: Optional[str] = None
    cusip: Optional[str] = None
    asset_class: str
    type: str
    issuer: str
    maturity_date: Optional[date] = None
    coupon_rate: Optional[float] = None
    quantidade: float
    preco_usd: float
    posicao_usd: float
    posicao_brl: float
    posicao_anterior_usd: float
    variacion_usd: float
    variacion_pct: Optional[float] = None
    match_status: Literal["EXACT", "MAPPED", "NEW"]
    instrument_id: Optional[int] = None
    instrument_name_bd: Optional[str] = None
    balance_usd_bd: Optional[float] = None
    diff_status: Literal["NEW", "UPDATED", "UNCHANGED", "DISAPPEARED"]
    warnings: List[str] = []


class DividendDiffItem(BaseModel):
    pay_date: date
    symbol: Optional[str] = None
    cusip: Optional[str] = None
    dividend_per_share: float
    shares: float
    valor_liquido_usd: float
    valor_liquido_brl: float
    withholding_rate: float
    match_status: Literal["EXACT", "MAPPED", "NEW"]
    instrument_id: Optional[int] = None
    instrument_name_bd: Optional[str] = None
    dup_status: Literal["NEW", "DUPLICATE"]


# ─── PDF Parsing ──────────────────────────────────────────────────────────────

def _parse_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    cleaned = s.replace(",", "").replace("%", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_us_date(s: str) -> Optional[date]:
    """Parse MM/DD/YYYY → date."""
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y").date()
    except (ValueError, TypeError):
        return None


def _parse_short_date(s: str) -> Optional[date]:
    """Parse MM/DD/YY → date."""
    try:
        return datetime.strptime(s.strip(), "%m/%d/%y").date()
    except (ValueError, TypeError):
        return None


def _merge_symbol_cusip_rows(raw_rows: list) -> list:
    """
    pdfplumber may return CUSIP as a separate row with only col[1] filled.
    Merge such rows into the previous row.
    """
    merged = []
    for row in raw_rows:
        if not row:
            continue
        # Check if this is a CUSIP-only row: col[1] has content, rest are empty/None
        non_empty = [i for i, c in enumerate(row) if c and str(c).strip()]
        if non_empty == [1] and merged:
            # This row contains only the CUSIP/symbol for the previous instrument
            prev = merged[-1]
            if prev.get("cusip") is None:
                prev["cusip"] = str(row[1]).strip()
        else:
            merged.append({"_raw": row})
    return merged


def _extract_symbol_cusip(cell: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Handle 'RDVY\n33738R506' or just 'RDVY' in a single cell."""
    if not cell:
        return None, None
    parts = str(cell).strip().split("\n")
    symbol = parts[0].strip() if parts[0].strip() else None
    cusip = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return symbol, cusip


def _is_header_row(row: list) -> bool:
    joined = " ".join(str(c) for c in row if c).lower()
    return "descrição" in joined and ("quantidade" in joined or "preço" in joined)


def _is_total_row(row: list) -> bool:
    first = str(row[0]).strip().lower() if row and row[0] else ""
    return first in ("total", "totais", "total da carteira")


def parse_period_dates(pdf_bytes: bytes) -> Tuple[Optional[date], Optional[date]]:
    """Extract period_start and period_end from the first page of the PDF."""
    import pdfplumber
    with pdfplumber.open(__import__("io").BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    # Pattern: "Data do extrato: 2026-03-01 - 2026-03-31"
    m = re.search(r"Data do extrato[:\s]+(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        try:
            start = date.fromisoformat(m.group(1))
            end = date.fromisoformat(m.group(2))
            return start, end
        except ValueError:
            pass
    return None, None


def parse_account_number(pdf_bytes: bytes) -> Optional[str]:
    import pdfplumber
    with pdfplumber.open(__import__("io").BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    m = re.search(r"\b(\d[A-Z]{2}\d{5,})\b", text)
    if m:
        return m.group(1)
    return None


def _parse_carteira_table(pdf_bytes: bytes) -> Tuple[List[ParsedPosition], float, List[str]]:
    """Extract positions from the CARTEIRA table."""
    import pdfplumber
    positions = []
    total_usd = 0.0
    warnings = []

    with pdfplumber.open(__import__("io").BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                # Find header row
                header_idx = None
                for i, row in enumerate(table):
                    if row and _is_header_row(row):
                        header_idx = i
                        break
                if header_idx is None:
                    continue

                data_rows = table[header_idx + 1:]

                # First pass: merge CUSIP-only rows
                parsed_rows = []
                i = 0
                while i < len(data_rows):
                    row = data_rows[i]
                    if not row or not any(c and str(c).strip() for c in row):
                        i += 1
                        continue
                    # Check if this is a CUSIP-only row (only col 1 has content)
                    non_empty_cols = [j for j, c in enumerate(row) if c and str(c).strip()]
                    if non_empty_cols == [1] and parsed_rows:
                        # Merge into previous row's cusip
                        parsed_rows[-1]["cusip"] = str(row[1]).strip()
                        i += 1
                        continue
                    # Normal row
                    parsed_rows.append({"row": row, "cusip": None})
                    i += 1

                for item in parsed_rows:
                    row = item["row"]
                    extra_cusip = item.get("cusip")

                    # Skip total row
                    if _is_total_row(row):
                        # Try to extract total
                        for cell in row[1:]:
                            v = _parse_float(str(cell) if cell else "")
                            if v and v > 1000:
                                total_usd = v
                        continue

                    if len(row) < 5:
                        continue

                    descricao = str(row[0]).strip() if row[0] else ""
                    if not descricao:
                        continue

                    # Col 1: symbol / CUSIP (may contain \n)
                    symbol, cusip_inline = _extract_symbol_cusip(str(row[1]) if row[1] else "")
                    cusip = extra_cusip or cusip_inline

                    quantidade = _parse_float(str(row[2]) if row[2] else "")
                    # col 3 is "ativos alugados" — skip
                    preco_usd = _parse_float(str(row[4]) if len(row) > 4 and row[4] else "")
                    posicao_usd = _parse_float(str(row[5]) if len(row) > 5 and row[5] else "")
                    posicao_anterior = _parse_float(str(row[6]) if len(row) > 6 and row[6] else "")
                    pct_carteira = _parse_float(str(row[8]) if len(row) > 8 and row[8] else "")

                    if quantidade is None or preco_usd is None or posicao_usd is None:
                        warnings.append(f"Fila incompleta ignorada: {descricao[:50]}")
                        continue

                    positions.append(ParsedPosition(
                        descricao=descricao,
                        symbol=symbol,
                        cusip=cusip,
                        quantidade=quantidade,
                        preco_usd=preco_usd,
                        posicao_usd=posicao_usd,
                        posicao_anterior_usd=posicao_anterior or 0.0,
                        pct_carteira=pct_carteira or 0.0,
                    ))

    return positions, total_usd, warnings


def parse_atividade(pdf_bytes: bytes) -> Tuple[List[ParsedDividend], List[str]]:
    """Extract CASH_DIVIDEND events from the ATIVIDADE table."""
    import pdfplumber
    dividends = []
    warnings = []

    with pdfplumber.open(__import__("io").BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                # Find header with "Tipo de transação" and "Valor líquido"
                header_idx = None
                for i, row in enumerate(table):
                    joined = " ".join(str(c) for c in row if c).lower()
                    if "tipo de transa" in joined and ("valor" in joined or "líquido" in joined):
                        header_idx = i
                        break
                if header_idx is None:
                    continue

                header = table[header_idx]
                # Detect column indices
                tipo_col = next((j for j, h in enumerate(header) if h and "tipo" in str(h).lower()), 0)
                symbol_col = next((j for j, h in enumerate(header) if h and "símbolo" in str(h).lower()), 1)
                desc_col = next((j for j, h in enumerate(header) if h and "descri" in str(h).lower()), 2)
                date_col = next((j for j, h in enumerate(header) if h and "data" in str(h).lower()), 3)
                valor_col = next((j for j, h in enumerate(header) if h and "valor" in str(h).lower()), 4)

                for row in table[header_idx + 1:]:
                    if not row or not any(c and str(c).strip() for c in row):
                        continue
                    tipo = str(row[tipo_col]).strip() if row[tipo_col] else ""
                    if tipo.upper() != "CASH_DIVIDEND":
                        continue

                    symbol_cell = str(row[symbol_col]).strip() if len(row) > symbol_col and row[symbol_col] else ""
                    symbol, cusip = _extract_symbol_cusip(symbol_cell)

                    desc = str(row[desc_col]).strip() if len(row) > desc_col and row[desc_col] else ""
                    valor_liquido = _parse_float(str(row[valor_col]) if len(row) > valor_col and row[valor_col] else "")

                    if valor_liquido is None:
                        warnings.append(f"Dividendo sin valor líquido: {desc[:50]}")
                        continue

                    # Parse description fields
                    div_match = re.search(r"Cash Div of ([\d.]+) on ([\d.]+) shs\.", desc)
                    pay_match = re.search(r"Pay (\d{2}/\d{2}/\d{2})", desc)
                    rec_match = re.search(r"Rec (\d{2}/\d{2}/\d{2})", desc)
                    wht_match = re.search(r"(\d+)%\s*NON Resident Alien Withholding", desc, re.IGNORECASE)

                    dividend_per_share = float(div_match.group(1)) if div_match else 0.0
                    shares = float(div_match.group(2)) if div_match else 0.0
                    pay_date = _parse_short_date(pay_match.group(1)) if pay_match else None
                    rec_date = _parse_short_date(rec_match.group(1)) if rec_match else None
                    withholding_rate = float(wht_match.group(1)) / 100.0 if wht_match else 0.0

                    # Try date column as fallback for pay_date
                    if pay_date is None and len(row) > date_col and row[date_col]:
                        date_str = str(row[date_col]).strip()
                        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
                            try:
                                pay_date = datetime.strptime(date_str, fmt).date()
                                break
                            except ValueError:
                                pass

                    if pay_date is None:
                        warnings.append(f"Dividendo sin fecha de pago: {desc[:50]}")
                        continue

                    dividends.append(ParsedDividend(
                        pay_date=pay_date,
                        rec_date=rec_date,
                        symbol=symbol,
                        cusip=cusip,
                        shares=shares,
                        dividend_per_share=dividend_per_share,
                        valor_liquido_usd=valor_liquido,
                        withholding_rate=withholding_rate,
                    ))

    return dividends, warnings


def parse_xp_international_pdf(pdf_bytes: bytes) -> ParsedReport:
    """Main entry point: parse a full XP International PDF statement."""
    warnings: List[str] = []

    period_start, period_end = parse_period_dates(pdf_bytes)
    account_number = parse_account_number(pdf_bytes)
    positions, total_usd, pos_warnings = _parse_carteira_table(pdf_bytes)
    dividends, div_warnings = parse_atividade(pdf_bytes)

    warnings.extend(pos_warnings)
    warnings.extend(div_warnings)

    return ParsedReport(
        period_start=period_start,
        period_end=period_end,
        account_number=account_number,
        positions=positions,
        dividends=dividends,
        total_portfolio_usd=total_usd,
        parse_warnings=warnings,
    )


# ─── Classification ───────────────────────────────────────────────────────────

def classify_international(parsed: ParsedPosition) -> InstrumentClassification:
    descricao = parsed.descricao

    if UST_MARKER in descricao.upper():
        return InstrumentClassification(
            asset_class="UST",
            type="renta_fija",
            issuer="United States Treasury",
        )

    bond_match = BOND_PATTERN.search(descricao)
    if bond_match:
        coupon_rate = float(bond_match.group(1))
        maturity_date = _parse_us_date(bond_match.group(2))
        issuer = descricao[:bond_match.start()].strip().rstrip(",").strip()
        return InstrumentClassification(
            asset_class="CORP_BOND",
            type="renta_fija",
            issuer=issuer,
            coupon_rate=coupon_rate,
            maturity_date=maturity_date,
        )

    # ETF / equity
    return InstrumentClassification(
        asset_class="ETF",
        type="accion",
        issuer=descricao,
        ticker_for_prices=parsed.symbol,
    )


# ─── Matching ─────────────────────────────────────────────────────────────────

def match_instrument(
    parsed: ParsedPosition,
    classification: InstrumentClassification,
    db: Session,
) -> MatchResult:
    # Step 1: match by CUSIP
    if parsed.cusip:
        inst = (
            db.query(Instrument)
            .filter(
                Instrument.ticker == parsed.cusip,
                Instrument.custodian == "XP_INTERNATIONAL",
            )
            .first()
        )
        if inst:
            return MatchResult(status="EXACT", instrument_id=inst.id, match_key=f"cusip:{parsed.cusip}")

    # Step 2: match by symbol/ticker
    if parsed.symbol:
        inst = (
            db.query(Instrument)
            .filter(
                Instrument.ticker == parsed.symbol,
                Instrument.custodian == "XP_INTERNATIONAL",
            )
            .first()
        )
        if inst:
            return MatchResult(status="EXACT", instrument_id=inst.id, match_key=f"ticker:{parsed.symbol}")

    # Step 3: check instrument_code_mappings
    keys_to_check = [k for k in [parsed.cusip, parsed.symbol] if k]
    for key in keys_to_check:
        mapping = db.query(InstrumentCodeMapping).filter(InstrumentCodeMapping.codigo_excel == key).first()
        if mapping:
            return MatchResult(status="MAPPED", instrument_id=mapping.instrument_id, match_key=f"mapping:{key}")

    return MatchResult(status="NEW", instrument_id=None, match_key="")


# ─── USD/BRL Rate ─────────────────────────────────────────────────────────────

def get_usd_brl_rate(reference_date: date) -> Optional[float]:
    try:
        import yfinance as yf
        start = reference_date - timedelta(days=7)
        end = reference_date + timedelta(days=1)
        data = yf.download("BRL=X", start=start, end=end, progress=False, auto_adjust=True)
        if data.empty:
            return None
        close = data["Close"]
        if hasattr(close, "iloc"):
            val = float(close.iloc[-1])
            return val if val > 0 else None
    except Exception:
        pass
    return None


# ─── Diff Computation ─────────────────────────────────────────────────────────

def compute_position_diffs(
    positions: List[ParsedPosition],
    usd_brl_rate: float,
    period_date: date,
    db: Session,
) -> List[InternationalDiffItem]:
    diffs = []
    for pos in positions:
        classification = classify_international(pos)
        match = match_instrument(pos, classification, db)
        warnings: List[str] = []

        posicao_brl = pos.posicao_usd * usd_brl_rate
        variacion_usd = pos.posicao_usd - pos.posicao_anterior_usd
        variacion_pct = None
        if pos.posicao_anterior_usd and pos.posicao_anterior_usd != 0:
            variacion_pct = (variacion_usd / pos.posicao_anterior_usd) * 100

        # Look up existing position in BD
        instrument_name_bd = None
        balance_usd_bd = None
        diff_status: Literal["NEW", "UPDATED", "UNCHANGED", "DISAPPEARED"] = "NEW"

        if match.instrument_id:
            inst = db.query(Instrument).filter(Instrument.id == match.instrument_id).first()
            instrument_name_bd = inst.name if inst else None

            existing_mp = (
                db.query(MonthlyPosition)
                .filter(
                    MonthlyPosition.instrument_id == match.instrument_id,
                    MonthlyPosition.date == period_date,
                    MonthlyPosition.custodian_override == "XP_INTERNATIONAL",
                )
                .first()
            )
            if existing_mp:
                balance_usd_bd = existing_mp.balance_usd
                if balance_usd_bd is not None and abs(balance_usd_bd - pos.posicao_usd) < 0.01:
                    diff_status = "UNCHANGED"
                else:
                    diff_status = "UPDATED"
            else:
                diff_status = "NEW"

        if match.status == "NEW":
            warnings.append("Sin match en BD — se creará nuevo instrumento si create_new_instruments=True")

        diffs.append(InternationalDiffItem(
            descricao=pos.descricao,
            symbol=pos.symbol,
            cusip=pos.cusip,
            asset_class=classification.asset_class,
            type=classification.type,
            issuer=classification.issuer,
            maturity_date=classification.maturity_date,
            coupon_rate=classification.coupon_rate,
            quantidade=pos.quantidade,
            preco_usd=pos.preco_usd,
            posicao_usd=pos.posicao_usd,
            posicao_brl=posicao_brl,
            posicao_anterior_usd=pos.posicao_anterior_usd,
            variacion_usd=variacion_usd,
            variacion_pct=variacion_pct,
            match_status=match.status,
            instrument_id=match.instrument_id,
            instrument_name_bd=instrument_name_bd,
            balance_usd_bd=balance_usd_bd,
            diff_status=diff_status,
            warnings=warnings,
        ))
    return diffs


def check_dividend_duplicates(
    dividends: List[ParsedDividend],
    usd_brl_rate: float,
    db: Session,
) -> List[DividendDiffItem]:
    items = []
    for div in dividends:
        # Build a fake ParsedPosition to reuse match_instrument
        fake_pos = ParsedPosition(
            descricao=div.symbol or "",
            symbol=div.symbol,
            cusip=div.cusip,
            quantidade=div.shares,
            preco_usd=div.dividend_per_share,
            posicao_usd=div.valor_liquido_usd,
            posicao_anterior_usd=0.0,
            pct_carteira=0.0,
        )
        classification = classify_international(fake_pos)
        match = match_instrument(fake_pos, classification, db)

        dup_status: Literal["NEW", "DUPLICATE"] = "NEW"
        if match.instrument_id:
            # Check if provento_item already exists for this instrument/date/amount
            existing = (
                db.query(ProvéntoItem)
                .filter(
                    ProvéntoItem.instrument_id == match.instrument_id,
                    ProvéntoItem.date == div.pay_date,
                    ProvéntoItem.amount_brl.between(
                        div.valor_liquido_usd * usd_brl_rate * 0.999,
                        div.valor_liquido_usd * usd_brl_rate * 1.001,
                    ),
                    ProvéntoItem.source == "XP_INTERNATIONAL_PDF",
                )
                .first()
            )
            if existing:
                dup_status = "DUPLICATE"

        instrument_name_bd = None
        if match.instrument_id:
            inst = db.query(Instrument).filter(Instrument.id == match.instrument_id).first()
            instrument_name_bd = inst.name if inst else None

        items.append(DividendDiffItem(
            pay_date=div.pay_date,
            symbol=div.symbol,
            cusip=div.cusip,
            dividend_per_share=div.dividend_per_share,
            shares=div.shares,
            valor_liquido_usd=div.valor_liquido_usd,
            valor_liquido_brl=div.valor_liquido_usd * usd_brl_rate,
            withholding_rate=div.withholding_rate,
            match_status=match.status,
            instrument_id=match.instrument_id,
            instrument_name_bd=instrument_name_bd,
            dup_status=dup_status,
        ))
    return items


# ─── Apply Import ─────────────────────────────────────────────────────────────

def _get_or_create_instrument(diff: InternationalDiffItem, db: Session) -> int:
    """Create a new Instrument from the diff classification data."""
    ticker = diff.cusip or diff.symbol
    inst = Instrument(
        name=diff.descricao,
        ticker=ticker,
        custodian="XP_INTERNATIONAL",
        type=diff.type,
        location="exterior",
        currency="USD",
        asset_class=diff.asset_class,
        maturity_date=diff.maturity_date,
        status="activo",
        pays_dividends=(diff.asset_class == "ETF"),
    )
    db.add(inst)
    db.flush()
    return inst.id


def apply_import_positions(
    diffs: List[InternationalDiffItem],
    config: InternationalImportConfig,
    skip_keys: List[str],
    manual_mappings: Dict[str, int],
    db: Session,
) -> dict:
    period_date = date.fromisoformat(config.period_date)
    new_instruments = 0
    new_positions = 0
    updated_positions = 0
    skipped = 0

    for diff in diffs:
        skip_key = diff.cusip or diff.symbol or diff.descricao
        if skip_key in skip_keys:
            skipped += 1
            continue

        instrument_id = diff.instrument_id

        # Apply manual mapping override
        if skip_key in manual_mappings:
            instrument_id = manual_mappings[skip_key]

        # Create new instrument if needed
        if instrument_id is None:
            if not config.create_new_instruments:
                skipped += 1
                continue
            instrument_id = _get_or_create_instrument(diff, db)
            new_instruments += 1

        # Upsert MonthlyPosition
        mp = (
            db.query(MonthlyPosition)
            .filter(
                MonthlyPosition.instrument_id == instrument_id,
                MonthlyPosition.date == period_date,
                MonthlyPosition.custodian_override == "XP_INTERNATIONAL",
            )
            .first()
        )
        is_new = mp is None
        if mp is None:
            mp = MonthlyPosition(
                instrument_id=instrument_id,
                date=period_date,
                custodian_override="XP_INTERNATIONAL",
            )
            db.add(mp)

        mp.balance_usd = diff.posicao_usd
        mp.balance_brl = diff.posicao_brl
        mp.usd_rate = config.usd_brl_rate
        if config.import_quantities:
            mp.quantity = diff.quantidade
        if config.import_unit_price:
            mp.unit_price = diff.preco_usd

        if is_new:
            new_positions += 1
        else:
            updated_positions += 1

    db.commit()
    return {
        "new_instruments": new_instruments,
        "new_positions": new_positions,
        "updated_positions": updated_positions,
        "skipped": skipped,
    }


def apply_import_dividends(
    dividend_diffs: List[DividendDiffItem],
    config: InternationalImportConfig,
    skip_indices: List[int],
    manual_mappings: Dict[str, int],
    db: Session,
) -> dict:
    created = 0
    skipped_duplicates = 0
    skipped_manual = 0

    for i, div in enumerate(dividend_diffs):
        if i in skip_indices:
            skipped_manual += 1
            continue
        if div.dup_status == "DUPLICATE":
            skipped_duplicates += 1
            continue

        instrument_id = div.instrument_id
        skip_key = div.cusip or div.symbol or ""
        if skip_key in manual_mappings:
            instrument_id = manual_mappings[skip_key]

        if instrument_id is None:
            skipped_manual += 1
            continue

        item = ProvéntoItem(
            instrument_id=instrument_id,
            date=div.pay_date,
            amount_brl=div.valor_liquido_brl,
            type="dividendo",
            source="XP_INTERNATIONAL_PDF",
            raw_event_type="CASH_DIVIDEND",
        )
        db.add(item)
        created += 1

    db.commit()
    return {
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "skipped_manual": skipped_manual,
    }


# ─── Token Cache ──────────────────────────────────────────────────────────────

def _purge_expired():
    now = datetime.utcnow()
    expired = [t for t, v in _TOKEN_CACHE.items() if v["expires"] < now]
    for t in expired:
        del _TOKEN_CACHE[t]


def store_preview(
    report: ParsedReport,
    position_diffs: List[InternationalDiffItem],
    dividend_diffs: List[DividendDiffItem],
    usd_brl_rate_suggested: Optional[float],
) -> str:
    _purge_expired()
    token = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)
    _TOKEN_CACHE[token] = {
        "report": report,
        "position_diffs": position_diffs,
        "dividend_diffs": dividend_diffs,
        "usd_brl_rate_suggested": usd_brl_rate_suggested,
        "expires": expires,
    }
    return token


def load_preview(token: str) -> Optional[dict]:
    _purge_expired()
    entry = _TOKEN_CACHE.get(token)
    if entry and entry["expires"] > datetime.utcnow():
        return entry
    return None
