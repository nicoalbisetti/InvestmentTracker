from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models.monthly_position import MonthlyPosition
from app.models.instrument import Instrument
from app.services.performance import (
    calculate_cagr, calculate_drawdown, calculate_volatility, calculate_cumulative_return
)

router = APIRouter(prefix="/api/history", tags=["history"])


def _position_to_dict(pos):
    return {
        "date": pos.date.isoformat(),
        "balance_brl": pos.balance_brl,
        "gain": pos.gain,
        "gain_pct": pos.gain_pct,
        "applications": pos.applications,
        "redemptions": pos.redemptions,
    }


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
