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
    cleaned = s.replace(".", "").replace(",", ".").replace("%", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_short_date(s: str) -> Optional[date]:
    """Parse MM/DD/YY → date."""
    try:
        return datetime.strptime(s.strip(), "%m/%d/%y").date()
    except (ValueError, TypeError):
        return None


def parse_period_dates(pdf_bytes: bytes) -> Tuple[Optional[date], Optional[date]]:
    import pdfplumber
    with pdfplumber.open(__import__("io").BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text() or ""
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


def parse_xp_international_pdf(pdf_bytes: bytes) -> ParsedReport:
    """Main entry point: parse a full XP International PDF statement using text extraction."""
    import pdfplumber
    warnings: List[str] = []

    period_start, period_end = parse_period_dates(pdf_bytes)
    account_number = parse_account_number(pdf_bytes)

    pages_text = []
    with pdfplumber.open(__import__("io").BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)
                
    full_text = "\n".join(pages_text)
    lines = full_text.split('\n')
    
    positions = []
    in_carteira = False
    
    pos_line_re = re.compile(r'^(.*?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)$')
    curr_pos = None
    total_usd = 0.0

    for line in lines:
        line = line.strip()
        if not line: continue
        
        if line == "CARTEIRA":
            in_carteira = True
            continue
            
        if in_carteira:
            if line.startswith("Total ") and "CARTEIRA" not in line:
                in_carteira = False
                try:
                    total_usd = float(line.split()[1].replace(".", "").replace(",", "."))
                except:
                    pass
                continue
            if "Descrição Símbolo" in line or "CUSIP anterior" in line:
                continue
            
            m = pos_line_re.match(line)
            if m:
                if curr_pos:
                    positions.append(curr_pos)
                
                desc_sym = m.group(1).split()
                symbol = None
                if len(desc_sym) > 1 and len(desc_sym[-1]) <= 5 and desc_sym[-1].isupper() and desc_sym[-1].isalpha():
                    symbol = desc_sym[-1]
                    desc = " ".join(desc_sym[:-1])
                else:
                    desc = " ".join(desc_sym)
                
                curr_pos = ParsedPosition(
                    descricao=desc,
                    symbol=symbol,
                    cusip=None,
                    quantidade=_parse_float(m.group(2)) or 0.0,
                    preco_usd=_parse_float(m.group(4)) or 0.0,
                    posicao_usd=_parse_float(m.group(5)) or 0.0,
                    posicao_anterior_usd=_parse_float(m.group(6)) or 0.0,
                    pct_carteira=_parse_float(m.group(8)) or 0.0,
                )
            elif curr_pos:
                tokens = line.split()
                if len(tokens[-1]) == 9 and tokens[-1].isalnum():
                    curr_pos.cusip = tokens[-1]
                    if len(tokens) > 1:
                        curr_pos.descricao += " " + " ".join(tokens[:-1])
                else:
                    curr_pos.descricao += " " + line
                    
    if curr_pos:
        positions.append(curr_pos)

    # Dividends
    dividends = []
    div_blocks = re.findall(r'(\d{4}-\d{2}-\d{2})\s+CASH_DIVIDEND\s+(.*?)(?=\d{4}-\d{2}-\d{2}\s+(?:CASH_DIVIDEND|TRANSFER)|$)', full_text, re.DOTALL)
    
    for date_str, block in div_blocks:
        block_clean = " ".join(block.split())
        
        m_val = re.search(r'0,00\s+([\d.,]+)\s+0,00', block_clean)
        val_usd = _parse_float(m_val.group(1)) if m_val else 0.0
        
        m_div = re.search(r'(?:Div|of)\s+([\d.]+)\s+on\s+([\d.]+)\s+shs', block_clean)
        div_per_share = float(m_div.group(1)) if m_div else 0.0
        shares = float(m_div.group(2)) if m_div else 0.0
        
        m_cusip = re.search(r'\b([A-Z0-9]{9})\b', block_clean)
        cusip = m_cusip.group(1) if m_cusip else None
        
        m_wht = re.search(r'(\d+)%\s*NON Resident Alien', block_clean, re.IGNORECASE)
        wht = float(m_wht.group(1))/100.0 if m_wht else 0.0
        
        m_pay = re.search(r'Pay\s+(\d{2}/\d{2}/\d{2})', block_clean)
        if m_pay:
            pay_date = _parse_short_date(m_pay.group(1))
        else:
            try:
                pay_date = date.fromisoformat(date_str)
            except:
                pay_date = date.today() # fallback
                
        symbol = None
        if m_val:
            prefix = block_clean[:m_val.start()].strip()
            prefix_tokens = prefix.split()
            if prefix_tokens and len(prefix_tokens[-1]) <= 5 and prefix_tokens[-1].isupper():
                symbol = prefix_tokens[-1]
                
        dividends.append(ParsedDividend(
            pay_date=pay_date, # type: ignore
            rec_date=None,
            symbol=symbol,
            cusip=cusip,
            shares=shares,
            dividend_per_share=div_per_share,
            valor_liquido_usd=val_usd, # type: ignore
            withholding_rate=wht,
        ))

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
