import io
import csv
from datetime import date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.services.snapshot_sync import sync_snapshot_for_date, sync_all_snapshots, resync_portfolio_totals
from app.services.return_calculator import compute_period_return, PRICE_TYPES

TYPE_ORDER = ["accion", "fii", "renta_fija", "fundo", "previdencia", "prestamos", "saving", "fgts", "outro"]

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("/custodians")
def get_custodians(db: Session = Depends(get_db)):
    """Return distinct custodian values present in instruments."""
    rows = (
        db.query(Instrument.custodian)
        .filter(Instrument.custodian.isnot(None), Instrument.status == "activo")
        .distinct()
        .order_by(Instrument.custodian)
        .all()
    )
    return [r[0] for r in rows]


def _latest_positions_subquery(db: Session, month: Optional[str] = None):
    """Subquery: balance per instrument for a given month (YYYY-MM), or latest if not specified."""
    if month:
        # Exact month: first-of-month date
        target_date = date(int(month[:4]), int(month[5:7]), 1)
        return (
            db.query(
                MonthlyPosition.id.label("mp_id"),
                MonthlyPosition.instrument_id.label("iid"),
                MonthlyPosition.balance_brl.label("balance"),
                MonthlyPosition.balance_usd.label("balance_usd"),
                MonthlyPosition.unit_price.label("unit_price"),
                MonthlyPosition.avg_price.label("avg_price"),
                MonthlyPosition.quantity.label("quantity"),
                MonthlyPosition.date.label("pos_date"),
            )
            .filter(
                MonthlyPosition.date == target_date,
                MonthlyPosition.custodian_override.is_(None),
            )
            .subquery()
        )
    max_date_sub = (
        db.query(
            MonthlyPosition.instrument_id.label("iid"),
            func.max(MonthlyPosition.date).label("mdate"),
        )
        .filter(MonthlyPosition.custodian_override.is_(None))
        .group_by(MonthlyPosition.instrument_id)
        .subquery()
    )
    return (
        db.query(
            MonthlyPosition.id.label("mp_id"),
            MonthlyPosition.instrument_id.label("iid"),
            MonthlyPosition.balance_brl.label("balance"),
            MonthlyPosition.balance_usd.label("balance_usd"),
            MonthlyPosition.unit_price.label("unit_price"),
            MonthlyPosition.avg_price.label("avg_price"),
            MonthlyPosition.quantity.label("quantity"),
            MonthlyPosition.date.label("pos_date"),
        )
        .join(
            max_date_sub,
            (MonthlyPosition.instrument_id == max_date_sub.c.iid) &
            (MonthlyPosition.date == max_date_sub.c.mdate),
        )
        .filter(MonthlyPosition.custodian_override.is_(None))
        .subquery()
    )


def _build_query(
    db: Session,
    latest: any,
    custodian: Optional[str],
    type: Optional[str],
    currency: Optional[str],
    location: Optional[str],
    status: Optional[str],
    search: Optional[str],
    sort: str,
    order: str,
    with_position: bool = False,
    historical: bool = False,
):
    query = (
        db.query(Instrument, latest.c.balance, latest.c.balance_usd, latest.c.unit_price, latest.c.avg_price, latest.c.quantity, latest.c.mp_id, latest.c.pos_date)
        .outerjoin(latest, Instrument.id == latest.c.iid)
    )

    if historical:
        # Historical view: show all instruments that had positions in that month, regardless of current status
        if status:
            query = query.filter(Instrument.status == status)
        # No default status filter when historical
    elif status:
        query = query.filter(Instrument.status == status)
    else:
        query = query.filter(Instrument.status == "activo")

    if with_position:
        query = query.filter(latest.c.balance.isnot(None), latest.c.balance > 0)

    if custodian:
        query = query.filter(Instrument.custodian.ilike(f"%{custodian}%"))
    if type:
        query = query.filter(Instrument.type == type)
    if currency:
        query = query.filter(Instrument.currency == currency)
    if location:
        query = query.filter(Instrument.location == location)
    if search:
        query = query.filter(Instrument.name.ilike(f"%{search}%"))

    # Sort: balance maps to the joined column; other fields map to Instrument columns
    if sort == "default":
        location_order = case(
            (Instrument.location == "brasil", 0),
            (Instrument.location == "exterior", 1),
            else_=2,
        )
        type_order = case(
            *[(Instrument.type == t, i) for i, t in enumerate(TYPE_ORDER)],
            else_=99,
        )
        query = query.order_by(location_order, type_order, Instrument.name)
    else:
        if sort in ("current_balance_brl", "balance_brl"):
            sort_col = latest.c.balance
        elif sort == "balance_usd":
            sort_col = latest.c.balance_usd
        else:
            sort_col = getattr(Instrument, sort, None) or latest.c.balance
        query = query.order_by(sort_col.desc().nullslast() if order == "desc" else sort_col.asc().nullslast())
    return query


@router.get("")
def get_positions(
    custodian: Optional[str] = None,
    type: Optional[str] = None,
    currency: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    month: Optional[str] = Query(None, description="YYYY-MM to view a specific month"),
    sort: str = Query("current_balance_brl"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    with_position: bool = Query(False),
    db: Session = Depends(get_db),
):
    historical = month is not None
    latest = _latest_positions_subquery(db, month=month)
    query = _build_query(db, latest, custodian, type, currency, location, status, search, sort, order, with_position, historical=historical)
    # Wrap as subquery to get accurate row count (avoids DISTINCT on multi-entity queries)
    count_sq = query.subquery()
    total = db.query(func.count()).select_from(count_sq).scalar()
    rows = query.offset((page - 1) * limit).limit(limit).all()

    # Compute portfolio total from latest positions for accurate portfolio_pct
    portfolio_total = (
        db.query(func.sum(latest.c.balance))
        .filter(latest.c.balance.isnot(None), latest.c.balance > 0)
        .scalar() or 0
    )

    # Totals across all matching instruments (not just current page)
    # Must apply same filters as the main query so the total matches what's shown
    totals_q = (
        db.query(func.sum(latest.c.balance), func.sum(latest.c.balance_usd))
        .select_from(latest)
        .join(Instrument, Instrument.id == latest.c.iid)
    )
    if not historical:
        totals_q = totals_q.filter(Instrument.status == (status or "activo"))
    elif status:
        totals_q = totals_q.filter(Instrument.status == status)
    if custodian:
        totals_q = totals_q.filter(Instrument.custodian.ilike(f"%{custodian}%"))
    if type:
        totals_q = totals_q.filter(Instrument.type == type)
    if currency:
        totals_q = totals_q.filter(Instrument.currency == currency)
    if location:
        totals_q = totals_q.filter(Instrument.location == location)
    if search:
        totals_q = totals_q.filter(Instrument.name.ilike(f"%{search}%"))
    if with_position:
        totals_q = totals_q.filter(latest.c.balance.isnot(None), latest.c.balance > 0)
    total_brl_sum, total_usd_sum = totals_q.one()

    items = []
    for inst, balance, balance_usd, unit_price, avg_price, quantity, mp_id, pos_date in rows:
        portfolio_pct = (balance / portfolio_total) if (balance and portfolio_total) else None
        items.append({
            "id": inst.id,
            "mp_id": mp_id,
            "name": inst.name,
            "custodian": inst.custodian,
            "type": inst.type,
            "currency": inst.currency,
            "status": inst.status,
            "balance_brl": balance,
            "balance_usd": balance_usd,
            "pos_date": pos_date.isoformat() if pos_date else None,
            "portfolio_pct": portfolio_pct,
            "return_1m": inst.return_1m,
            "return_3m": inst.return_3m,
            "return_6m": inst.return_6m,
            "return_12m": inst.return_12m,
            "return_source": inst.return_source,
            "rank_1m": inst.rank_1m,
            "maturity_date": inst.maturity_date.isoformat() if inst.maturity_date else None,
            "in_liquidation": inst.in_liquidation or False,
            "asset_class": inst.asset_class,
            "unit_price": unit_price,
            "avg_price": avg_price,
            "quantity": quantity,
            "location": inst.location,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "total_brl": total_brl_sum,
        "total_usd": total_usd_sum,
    }


@router.get("/export")
def export_positions(
    custodian: Optional[str] = None,
    type: Optional[str] = None,
    currency: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    latest = _latest_positions_subquery(db)
    query = _build_query(db, latest, custodian, type, currency, location, status, search, "current_balance_brl", "desc")
    rows = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Instrumento", "Custodio", "Tipo", "Moneda", "Estado",
        "Saldo BRL", "% Portfolio", "Ret 1M", "Ret 3M", "Ret 6M", "Ret 12M",
        "Rank 1M", "Liquidez", "Vencimiento"
    ])
    for inst, balance, balance_usd, unit_price, avg_price, quantity, mp_id, pos_date in rows:
        writer.writerow([
            inst.name, inst.custodian, inst.type, inst.currency, inst.status,
            balance, balance_usd, inst.portfolio_pct,
            inst.return_1m, inst.return_3m, inst.return_6m, inst.return_12m,
            inst.rank_1m, inst.liquidity,
            inst.maturity_date.isoformat() if inst.maturity_date else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=posiciones.csv"},
    )


@router.post("/update-equities-prices")
def update_equities_prices(
    month: Optional[str] = Query(None, description="YYYY-MM format, defaults to latest position date"),
    db: Session = Depends(get_db),
):
    """
    Fetch current B3 prices for active stocks (accion) and FIIs via Yahoo Finance,
    then update monthly_positions.balance_brl = quantity * current_price.
    """
    import yfinance as yf

    # Determine target month filter
    if month:
        rows = (
            db.query(Instrument, MonthlyPosition)
            .join(MonthlyPosition, MonthlyPosition.instrument_id == Instrument.id)
            .filter(
                Instrument.status == "activo",
                Instrument.type.in_(["accion", "fii"]),
                MonthlyPosition.balance_brl.isnot(None),
                MonthlyPosition.balance_brl > 0,
                func.strftime("%Y-%m", MonthlyPosition.date) == month,
            )
            .all()
        )
    else:
        latest_sq = _latest_positions_subquery(db)
        inst_ids = [
            row[0] for row in (
                db.query(latest_sq.c.iid)
                .join(Instrument, Instrument.id == latest_sq.c.iid)
                .filter(
                    Instrument.status == "activo",
                    Instrument.type.in_(["accion", "fii"]),
                    latest_sq.c.balance.isnot(None),
                    latest_sq.c.balance > 0,
                )
                .all()
            )
        ]
        rows = (
            db.query(Instrument, MonthlyPosition)
            .join(MonthlyPosition, MonthlyPosition.instrument_id == Instrument.id)
            .filter(Instrument.id.in_(inst_ids))
            .order_by(MonthlyPosition.date.desc())
            .all()
        )
        # Keep only latest position per instrument
        seen = set()
        deduped = []
        for inst, mp in rows:
            if inst.id not in seen:
                seen.add(inst.id)
                deduped.append((inst, mp))
        rows = deduped

    errors = []
    # Separate into two buckets: BRL instruments (B3, ticker + ".SA") and USD (exterior, no suffix)
    brl_ticker_map: dict = {}  # yahoo_symbol -> (inst, mp)
    usd_ticker_map: dict = {}  # yahoo_symbol -> (inst, mp)

    for inst, mp in rows:
        if not inst.ticker or not inst.ticker.strip():
            errors.append(f"{inst.name}: ticker vacío")
            continue
        if not mp.quantity:
            errors.append(f"{inst.ticker}: sin cantidad")
            continue
        ticker_raw = inst.ticker.strip()
        is_usd = inst.location == "exterior" or inst.currency == "USD"
        if is_usd:
            usd_ticker_map[ticker_raw] = (inst, mp)
        else:
            brl_ticker_map[f"{ticker_raw}.SA"] = (inst, mp)

    if not brl_ticker_map and not usd_ticker_map:
        return {"updated": 0, "skipped": len(errors), "errors": errors, "prices": []}

    def _fetch_close(symbols: list) -> dict:
        """Download latest close prices from yfinance. Returns {symbol: price}."""
        if not symbols:
            return {}
        try:
            data = yf.download(symbols, period="1d", progress=False, auto_adjust=True)
            if hasattr(data.columns, "levels"):
                row = data["Close"].iloc[-1]
                return {sym: float(row[sym]) for sym in symbols if sym in row}
            else:
                return {symbols[0]: float(data["Close"].iloc[-1])}
        except Exception as e:
            errors.append(f"yfinance error: {e}")
            return {}

    brl_prices = _fetch_close(list(brl_ticker_map.keys()))
    usd_prices = _fetch_close(list(usd_ticker_map.keys()))

    updated = 0
    prices_out = []

    # Process BRL instruments (B3)
    for yahoo_symbol, (inst, mp) in brl_ticker_map.items():
        current_price = brl_prices.get(yahoo_symbol)
        if not current_price or current_price != current_price:
            errors.append(f"{inst.ticker}: sin precio en Yahoo Finance")
            continue

        old_balance = mp.balance_brl or 0
        new_balance = mp.quantity * current_price
        old_price = mp.unit_price
        change_pct = ((current_price / old_price) - 1) * 100 if old_price else None

        mp.balance_brl = new_balance
        mp.unit_price = current_price
        updated += 1
        prices_out.append({
            "ticker": inst.ticker,
            "name": inst.name,
            "currency": "BRL",
            "quantity": mp.quantity,
            "ref_price": round(old_price, 2) if old_price else None,
            "current_price": round(current_price, 2),
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
            "old_balance": round(old_balance, 2),
            "new_balance": round(new_balance, 2),
        })

    # Process USD instruments (exterior / XP_INTERNATIONAL)
    for yahoo_symbol, (inst, mp) in usd_ticker_map.items():
        current_price_usd = usd_prices.get(yahoo_symbol)
        if not current_price_usd or current_price_usd != current_price_usd:
            errors.append(f"{inst.ticker}: sin precio en Yahoo Finance")
            continue

        old_balance_usd = mp.balance_usd or 0
        new_balance_usd = mp.quantity * current_price_usd
        old_price = mp.unit_price
        change_pct = ((current_price_usd / old_price) - 1) * 100 if old_price else None

        mp.balance_usd = new_balance_usd
        mp.unit_price = current_price_usd

        # Recalculate BRL balance using last known usd_rate on this position
        if mp.usd_rate and mp.usd_rate > 0:
            mp.balance_brl = new_balance_usd * mp.usd_rate

        updated += 1
        prices_out.append({
            "ticker": inst.ticker,
            "name": inst.name,
            "currency": "USD",
            "quantity": mp.quantity,
            "ref_price": round(old_price, 2) if old_price else None,
            "current_price": round(current_price_usd, 2),
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
            "old_balance": round(old_balance_usd, 2),
            "new_balance": round(new_balance_usd, 2),
        })

    db.commit()
    if updated > 0:
        resync_portfolio_totals(db)
        db.commit()
    return {"updated": updated, "skipped": len(errors), "errors": errors, "prices": prices_out}


@router.post("/ensure-month")
def ensure_month_position(payload: dict, db: Session = Depends(get_db)):
    """Ensure a MonthlyPosition exists for instrument+month. Creates an empty one if absent."""
    instrument_id = int(payload["instrument_id"])
    month = payload["month"]  # YYYY-MM
    target_date = date(int(month[:4]), int(month[5:7]), 1)

    mp = db.query(MonthlyPosition).filter_by(instrument_id=instrument_id, date=target_date).first()
    if not mp:
        mp = MonthlyPosition(instrument_id=instrument_id, date=target_date)
        db.add(mp)
        db.commit()
        db.refresh(mp)
        sync_snapshot_for_date(db, target_date)

    return {"mp_id": mp.id}


@router.post("/copy-previous-month")
def copy_previous_month(payload: dict, db: Session = Depends(get_db)):
    """
    Copy positions from the previous month for active instruments that don't have
    a position in the target month yet.
    """
    target_month = payload.get("target_month")
    if not target_month:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="target_month is required")

    target_date = date(int(target_month[:4]), int(target_month[5:7]), 1)
    prev_date = target_date - relativedelta(months=1)

    # Get active instruments
    active_insts = db.query(Instrument.id).filter(Instrument.status == "activo").all()
    active_inst_ids = [r[0] for r in active_insts]

    if not active_inst_ids:
        return {"copied": 0}

    # Positions in previous month — exclude custodian_override rows (import auxiliaries)
    prev_positions = db.query(MonthlyPosition).filter(
        MonthlyPosition.date == prev_date,
        MonthlyPosition.instrument_id.in_(active_inst_ids),
        MonthlyPosition.custodian_override.is_(None),
    ).all()

    # Positions already existing in target month
    curr_positions = db.query(MonthlyPosition).filter(
        MonthlyPosition.date == target_date,
        MonthlyPosition.instrument_id.in_(active_inst_ids)
    ).all()
    
    existing_keys = {(p.instrument_id, p.custodian_override) for p in curr_positions}

    copied = 0
    for p in prev_positions:
        key = (p.instrument_id, p.custodian_override)
        if key not in existing_keys:
            # We copy only balance and quantity fields, strictly avoiding flow fields like applications or gain.
            new_mp = MonthlyPosition(
                instrument_id=p.instrument_id,
                date=target_date,
                balance_brl=p.balance_brl,
                balance_usd=p.balance_usd,
                usd_rate=p.usd_rate,
                avg_price=p.avg_price,
                quantity=p.quantity,
                unit_price=p.unit_price,
                custodian_override=p.custodian_override,
                capital_invested=p.capital_invested
            )
            db.add(new_mp)
            copied += 1

    if copied > 0:
        db.flush()
        sync_snapshot_for_date(db, target_date)
        db.commit()

    return {"copied": copied, "target_month": target_month}


@router.patch("/{mp_id}/balance")
def update_position_balance(
    mp_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Update balance_brl or balance_usd of a monthly_position. Recalculates the other using snapshot usd_rate."""
    mp = db.query(MonthlyPosition).filter_by(id=mp_id).first()
    if not mp:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Posición no encontrada")

    inst = db.query(Instrument).filter_by(id=mp.instrument_id).first()

    snap = (
        db.query(PortfolioSnapshot)
        .filter(func.strftime("%Y-%m", PortfolioSnapshot.date) == mp.date.strftime("%Y-%m"))
        .first()
    )
    usd_rate = snap.usd_rate if snap and snap.usd_rate else None

    if "balance_brl" in payload and payload["balance_brl"] is not None:
        mp.balance_brl = float(payload["balance_brl"])
        if usd_rate:
            mp.balance_usd = round(mp.balance_brl / usd_rate, 2)
    elif "balance_usd" in payload and payload["balance_usd"] is not None:
        mp.balance_usd = float(payload["balance_usd"])
        if usd_rate:
            mp.balance_brl = round(mp.balance_usd * usd_rate, 2)
    elif "quantity" in payload and payload["quantity"] is not None:
        mp.quantity = float(payload["quantity"])

    db.flush()
    sync_snapshot_for_date(db, mp.date)
    db.commit()
    return {"mp_id": mp_id, "balance_brl": mp.balance_brl, "balance_usd": mp.balance_usd, "quantity": mp.quantity}


@router.post("/update-usd-rate")
def update_usd_rate(
    month: Optional[str] = Query(None, description="YYYY-MM format, defaults to current month"),
    db: Session = Depends(get_db),
):
    """Fetch current USD/BRL rate from Yahoo Finance and update portfolio_snapshot for the target month."""
    import yfinance as yf
    from datetime import datetime

    target_month = month or datetime.today().strftime("%Y-%m")

    try:
        tk = yf.Ticker("USDBRL=X")
        hist = tk.history(period="1d")
        if hist.empty:
            return {"updated": False, "error": "No se obtuvo cotización de Yahoo Finance"}
        usd_rate = float(hist["Close"].iloc[-1])
    except Exception as e:
        return {"updated": False, "error": str(e)}

    # Update monthly_positions for target month
    positions = (
        db.query(MonthlyPosition, Instrument.location)
        .join(Instrument, Instrument.id == MonthlyPosition.instrument_id)
        .filter(func.strftime("%Y-%m", MonthlyPosition.date) == target_month)
        .all()
    )

    for mp, inst_location in positions:
        if inst_location == "exterior":
            # USD-denominated: recalculate BRL from USD balance × new rate
            if mp.balance_usd is not None:
                mp.balance_brl = round(mp.balance_usd * usd_rate, 2)
        else:
            # BRL-denominated: recalculate USD from BRL balance ÷ new rate
            if mp.balance_brl is not None and mp.balance_brl > 0:
                mp.balance_usd = round(mp.balance_brl / usd_rate, 2)

    # Update portfolio_snapshot
    snap = (
        db.query(PortfolioSnapshot)
        .filter(func.strftime("%Y-%m", PortfolioSnapshot.date) == target_month)
        .first()
    )
    old_rate = None
    if snap:
        old_rate = snap.usd_rate
        snap.usd_rate = usd_rate
        if snap.total_brl:
            snap.total_usd = snap.total_brl / usd_rate

    db.commit()
    return {
        "updated": True,
        "month": target_month,
        "old_rate": old_rate,
        "new_rate": round(usd_rate, 4),
        "positions_updated": len(positions),
    }


@router.get("/last-fixed-income-date")
def last_fixed_income_date(db: Session = Depends(get_db)):
    """Returns the most recent MonthlyPosition date for renta_fija instruments."""
    result = (
        db.query(func.max(MonthlyPosition.date))
        .join(Instrument, Instrument.id == MonthlyPosition.instrument_id)
        .filter(Instrument.type == "renta_fija")
        .scalar()
    )
    return {"date": result.isoformat() if result else None}


@router.get("/count-without-price")
def count_without_price(db: Session = Depends(get_db)):
    """Returns count of active renta_fija instruments with null current_balance_brl."""
    count = (
        db.query(Instrument)
        .filter(Instrument.type == "renta_fija", Instrument.status == "activo",
                Instrument.current_balance_brl.is_(None))
        .count()
    )
    return {"count": count}


@router.post("/recalculate-stats")
def recalculate_stats(db: Session = Depends(get_db)):
    """
    Recalculate current_balance_brl, portfolio_pct, return_1m/3m/6m/12m and
    rank_1m/3m/6m/12m for all active instruments using monthly_positions directly.
    """
    # Get latest balance per active instrument from monthly_positions
    latest_sq = _latest_positions_subquery(db)
    rows = (
        db.query(Instrument, latest_sq.c.balance, latest_sq.c.balance_usd, latest_sq.c.pos_date)
        .outerjoin(latest_sq, Instrument.id == latest_sq.c.iid)
        .filter(
            Instrument.status == "activo",
            latest_sq.c.balance.isnot(None),
            latest_sq.c.balance > 0,
        )
        .all()
    )

    total = sum(bal for _, bal, _, _ in rows if bal)
    total_usd = sum(usd for _, _, usd, _ in rows if usd)

    def _ret(n: int, iid: int, itype: str, ldate: date) -> Optional[float]:
        return compute_period_return(iid, itype, ldate, n, db)

    stats = {}
    for inst, current_bal, _, latest_date in rows:
        if not current_bal or not latest_date:
            continue

        r1m = _ret(1, inst.id, inst.type, latest_date)
        if r1m is not None:
            src = "price" if inst.type in PRICE_TYPES else "balance"
        else:
            src = "none"

        stats[inst.id] = {
            "current_balance_brl": current_bal,
            "portfolio_pct": current_bal / total if total else None,
            "return_1m": r1m,
            "return_3m": _ret(3, inst.id, inst.type, latest_date),
            "return_6m": _ret(6, inst.id, inst.type, latest_date),
            "return_12m": _ret(12, inst.id, inst.type, latest_date),
            "return_source": src,
        }

    # Compute ranks (1 = best return, only among instruments with that return available)
    for period, field in [("return_1m", "rank_1m"), ("return_3m", "rank_3m"),
                           ("return_6m", "rank_6m"), ("return_12m", "rank_12m")]:
        ranked = sorted(
            [(iid, s[period]) for iid, s in stats.items() if s[period] is not None],
            key=lambda x: x[1],
            reverse=True,
        )
        for rank, (iid, _) in enumerate(ranked, start=1):
            stats[iid][field] = rank

    # Apply to DB
    updated = 0
    instruments_map = {inst.id: inst for inst, _, _, _ in rows}
    for inst in instruments_map.values():
        s = stats.get(inst.id)
        if not s:
            continue
        inst.current_balance_brl = s.get("current_balance_brl")
        inst.portfolio_pct = s.get("portfolio_pct")
        inst.return_1m = s.get("return_1m")
        inst.return_3m = s.get("return_3m")
        inst.return_6m = s.get("return_6m")
        inst.return_12m = s.get("return_12m")
        inst.return_source = s.get("return_source")
        inst.rank_1m = s.get("rank_1m")
        inst.rank_3m = s.get("rank_3m")
        inst.rank_6m = s.get("rank_6m")
        inst.rank_12m = s.get("rank_12m")
        updated += 1

    db.commit()

    # Resync the latest portfolio snapshot totals from live monthly_positions data
    latest_snap = (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.date.desc())
        .first()
    )
    if latest_snap:
        # total_brl = sum of positions for the snapshot's own month
        month_total = (
            db.query(func.sum(MonthlyPosition.balance_brl))
            .filter(
                MonthlyPosition.date == latest_snap.date,
                MonthlyPosition.balance_brl.isnot(None),
                MonthlyPosition.balance_brl > 0,
            )
            .scalar() or 0
        )
        latest_snap.total_brl = month_total
        if latest_snap.usd_rate and latest_snap.usd_rate > 0:
            latest_snap.total_usd = month_total / latest_snap.usd_rate
        db.commit()

    return {"updated": updated, "total_portfolio": round(total, 2)}
