from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import date
from collections import defaultdict
from app.database import get_db
from app.models.monthly_position import MonthlyPosition
from app.models.instrument import Instrument
from app.services.performance import (
    calculate_cagr, calculate_drawdown, calculate_volatility, calculate_cumulative_return
)

router = APIRouter(prefix="/api/history", tags=["history"])


def _apply_instrument_filters(query, custodian=None, type_=None, market=None):
    if custodian:
        query = query.filter(Instrument.custodian == custodian)
    if type_:
        query = query.filter(Instrument.type == type_)
    elif market:
        if market == "exterior":
            query = query.filter(Instrument.type == "exterior")
        else:
            query = query.filter(Instrument.type != "exterior")
    return query


@router.get("/monthly")
def get_monthly_history(
    year: int,
    currency: str = Query("BRL"),
    custodian: Optional[str] = None,
    type: Optional[str] = None,
    market: Optional[str] = None,
    db: Session = Depends(get_db),
):
    inst_query = _apply_instrument_filters(db.query(Instrument), custodian, type, market)
    instruments = inst_query.all()
    instrument_ids = [i.id for i in instruments]

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 1)

    positions = (
        db.query(MonthlyPosition)
        .filter(
            MonthlyPosition.instrument_id.in_(instrument_ids),
            MonthlyPosition.date >= start_date,
            MonthlyPosition.date <= end_date,
        )
        .all()
    )

    # Aggregate by (instrument_id, month) — sum custodian_override duplicates
    pos_map: dict = defaultdict(lambda: defaultdict(lambda: None))
    for pos in positions:
        value = pos.balance_usd if currency == "USD" else pos.balance_brl
        if value is not None:
            month = pos.date.month
            current = pos_map[pos.instrument_id][month]
            pos_map[pos.instrument_id][month] = (current or 0) + value

    # Only include instruments with at least one value in this year
    instruments_with_data = [i for i in instruments if pos_map[i.id]]

    months = list(range(1, 13))
    items = []
    for inst in instruments_with_data:
        values = [pos_map[inst.id].get(m) for m in months]
        items.append({
            "instrument_id": inst.id,
            "name": inst.name,
            "custodian": inst.custodian,
            "type": inst.type,
            "values": values,
        })

    totals = []
    for m in months:
        total = None
        for inst in instruments_with_data:
            val = pos_map[inst.id].get(m)
            if val is not None:
                total = (total or 0) + val
        totals.append(total)

    return {
        "year": year,
        "currency": currency,
        "months": months,
        "items": items,
        "totals": totals,
    }


@router.get("/annual")
def get_annual_history(
    currency: str = Query("BRL"),
    custodian: Optional[str] = None,
    type: Optional[str] = None,
    market: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Determine last 10 years with any data
    years_rows = (
        db.query(func.strftime('%Y', MonthlyPosition.date).label('yr'))
        .distinct()
        .order_by(func.strftime('%Y', MonthlyPosition.date).desc())
        .limit(10)
        .all()
    )
    years = [int(r.yr) for r in years_rows]

    if not years:
        return {"currency": currency, "years": [], "items": [], "totals": []}

    inst_query = _apply_instrument_filters(db.query(Instrument), custodian, type, market)
    instruments = inst_query.all()
    instrument_ids = [i.id for i in instruments]

    min_year, max_year = min(years), max(years)
    positions = (
        db.query(MonthlyPosition)
        .filter(
            MonthlyPosition.instrument_id.in_(instrument_ids),
            MonthlyPosition.date >= date(min_year, 1, 1),
            MonthlyPosition.date <= date(max_year, 12, 1),
        )
        .all()
    )

    # Build map: {instrument_id: {year: {month: value}}}
    pos_map: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None)))
    for pos in positions:
        y = pos.date.year
        if y not in years:
            continue
        value = pos.balance_usd if currency == "USD" else pos.balance_brl
        if value is not None:
            m = pos.date.month
            current = pos_map[pos.instrument_id][y][m]
            pos_map[pos.instrument_id][y][m] = (current or 0) + value

    def get_annual_value(inst_id, yr):
        year_data = pos_map[inst_id].get(yr, {})
        if not year_data:
            return None
        # Prefer December, else last available month
        if year_data.get(12) is not None:
            return year_data[12]
        available = sorted([m for m, v in year_data.items() if v is not None], reverse=True)
        return year_data[available[0]] if available else None

    instruments_with_data = [
        i for i in instruments
        if any(get_annual_value(i.id, y) is not None for y in years)
    ]

    items = []
    for inst in instruments_with_data:
        items.append({
            "instrument_id": inst.id,
            "name": inst.name,
            "custodian": inst.custodian,
            "type": inst.type,
            "values": [get_annual_value(inst.id, y) for y in years],
        })

    totals = []
    for y in years:
        total = None
        for inst in instruments_with_data:
            val = get_annual_value(inst.id, y)
            if val is not None:
                total = (total or 0) + val
        totals.append(total)

    return {
        "currency": currency,
        "years": years,
        "items": items,
        "totals": totals,
    }


def _position_to_dict(pos):
    return {
        "date": pos.date.isoformat(),
        "balance_brl": pos.balance_brl,
        "gain": pos.gain,
        "gain_pct": pos.gain_pct,
        "applications": pos.applications,
        "redemptions": pos.redemptions,
    }


@router.get("/compare")
def compare_instruments(
    ids: str = Query(..., description="Comma-separated instrument IDs"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
):
    id_list = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    result = []
    for inst_id in id_list:
        inst = db.query(Instrument).filter_by(id=inst_id).first()
        if not inst:
            continue
        query = (
            db.query(MonthlyPosition)
            .filter(MonthlyPosition.instrument_id == inst_id)
            .order_by(MonthlyPosition.date.asc())
        )
        if date_from:
            query = query.filter(MonthlyPosition.date >= date_from)
        if date_to:
            query = query.filter(MonthlyPosition.date <= date_to)
        positions = query.all()
        result.append({
            "instrument": {"id": inst.id, "name": inst.name, "custodian": inst.custodian},
            "positions": [_position_to_dict(p) for p in positions],
        })
    return result


@router.get("/{instrument_id}")
def get_instrument_history(
    instrument_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
):
    inst = db.query(Instrument).filter_by(id=instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")

    query = (
        db.query(MonthlyPosition)
        .filter(MonthlyPosition.instrument_id == instrument_id)
        .order_by(MonthlyPosition.date.asc())
    )
    if date_from:
        query = query.filter(MonthlyPosition.date >= date_from)
    if date_to:
        query = query.filter(MonthlyPosition.date <= date_to)

    positions = query.all()
    values = [p.balance_brl for p in positions if p.balance_brl is not None]
    returns = [p.gain_pct for p in positions if p.gain_pct is not None]

    years = len(positions) / 12 if positions else 0
    cagr = calculate_cagr(values[0], values[-1], years) if len(values) >= 2 and years > 0 else None
    drawdown = calculate_drawdown(values)
    volatility = calculate_volatility(returns)
    total_return = calculate_cumulative_return(values[0], values[-1]) if len(values) >= 2 else None

    return {
        "instrument": {
            "id": inst.id,
            "name": inst.name,
            "custodian": inst.custodian,
            "type": inst.type,
        },
        "positions": [_position_to_dict(p) for p in positions],
        "metrics": {
            "cagr": cagr,
            "max_drawdown": drawdown,
            "volatility": volatility,
            "total_return": total_return,
            "periods": len(positions),
        },
    }
