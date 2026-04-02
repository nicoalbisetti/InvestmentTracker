from datetime import date, datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.equity_trade import EquityTrade
from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from app.schemas.equity_trade import (
    EquityTradeCreate,
    EquityTradeOut,
    EquityTradeSummary,
    EquityTradeUpdate,
)
from app.services.equity_recalculate import recalculate_equity_positions

router = APIRouter(prefix="/api/equity-trades", tags=["equity-trades"])


def _trade_to_out(trade: EquityTrade) -> dict:
    return {
        "id": trade.id,
        "instrument_id": trade.instrument_id,
        "date": trade.date,
        "trade_type": trade.trade_type,
        "quantity": trade.quantity,
        "price": trade.price,
        "amount_brl": trade.amount_brl,
        "notes": trade.notes,
        "created_at": trade.created_at,
        "instrument_name": trade.instrument.name if trade.instrument else "",
        "instrument_ticker": trade.instrument.ticker if trade.instrument else None,
    }


@router.get("/summary/{instrument_id}", response_model=EquityTradeSummary)
def get_summary(instrument_id: int, db: Session = Depends(get_db)):
    instrument = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")

    trades = db.query(EquityTrade).filter(EquityTrade.instrument_id == instrument_id).all()

    total_compras_qty = sum(t.quantity for t in trades if t.trade_type == "compra")
    total_ventas_qty = sum(t.quantity for t in trades if t.trade_type == "venta")
    qty_actual = total_compras_qty - total_ventas_qty

    compras = [t for t in trades if t.trade_type == "compra"]
    if compras:
        total_cost = sum(t.quantity * t.price for t in compras)
        avg_price_compra = total_cost / total_compras_qty if total_compras_qty > 0 else None
    else:
        avg_price_compra = None

    # Último precio: unit_price del mp más reciente
    last_mp = (
        db.query(MonthlyPosition)
        .filter(
            MonthlyPosition.instrument_id == instrument_id,
            MonthlyPosition.unit_price.isnot(None),
        )
        .order_by(MonthlyPosition.date.desc())
        .first()
    )
    ultimo_precio = last_mp.unit_price if last_mp else None

    pl_no_realizado = None
    pl_no_realizado_pct = None
    if ultimo_precio is not None and avg_price_compra is not None and qty_actual != 0:
        pl_no_realizado = qty_actual * (ultimo_precio - avg_price_compra)
        cost_basis = qty_actual * avg_price_compra
        if cost_basis != 0:
            pl_no_realizado_pct = (pl_no_realizado / abs(cost_basis)) * 100

    return EquityTradeSummary(
        instrument_id=instrument_id,
        instrument_name=instrument.name,
        instrument_ticker=instrument.ticker,
        total_compras_qty=total_compras_qty,
        total_ventas_qty=total_ventas_qty,
        qty_actual=qty_actual,
        avg_price_compra=avg_price_compra,
        ultimo_precio=ultimo_precio,
        pl_no_realizado=pl_no_realizado,
        pl_no_realizado_pct=pl_no_realizado_pct,
    )


@router.get("/")
def list_trades(
    instrument_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    trade_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(EquityTrade)
    if instrument_id:
        q = q.filter(EquityTrade.instrument_id == instrument_id)
    if date_from:
        q = q.filter(EquityTrade.date >= date_from)
    if date_to:
        q = q.filter(EquityTrade.date <= date_to)
    if trade_type and trade_type in ("compra", "venta"):
        q = q.filter(EquityTrade.trade_type == trade_type)

    total = q.count()
    trades = q.order_by(EquityTrade.date.desc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [_trade_to_out(t) for t in trades],
        "total": total,
        "page": page,
        "pages": max(1, ceil(total / limit)),
    }


@router.post("/")
def create_trade(body: EquityTradeCreate, db: Session = Depends(get_db)):
    instrument = db.query(Instrument).filter(Instrument.id == body.instrument_id).first()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")

    amount_brl = body.quantity * body.price

    trade = EquityTrade(
        instrument_id=body.instrument_id,
        date=body.date,
        trade_type=body.trade_type,
        quantity=body.quantity,
        price=body.price,
        amount_brl=amount_brl,
        notes=body.notes,
        created_at=datetime.utcnow(),
    )
    db.add(trade)
    db.flush()

    recalculated = recalculate_equity_positions(body.instrument_id, body.date, db)
    db.commit()
    db.refresh(trade)

    result = _trade_to_out(trade)
    result["recalculated_months"] = recalculated
    result["affected_from"] = body.date.strftime("%Y-%m")
    return result


@router.get("/{trade_id}", response_model=EquityTradeOut)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(EquityTrade).filter(EquityTrade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    return EquityTradeOut(**_trade_to_out(trade))


@router.put("/{trade_id}")
def update_trade(trade_id: int, body: EquityTradeUpdate, db: Session = Depends(get_db)):
    trade = db.query(EquityTrade).filter(EquityTrade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Operación no encontrada")

    old_date = trade.date

    if body.date is not None:
        trade.date = body.date
    if body.trade_type is not None:
        trade.trade_type = body.trade_type
    if body.quantity is not None:
        trade.quantity = body.quantity
    if body.price is not None:
        trade.price = body.price
    if body.notes is not None:
        trade.notes = body.notes

    trade.amount_brl = trade.quantity * trade.price

    from_date = min(old_date, trade.date)
    db.flush()

    recalculated = recalculate_equity_positions(trade.instrument_id, from_date, db)
    db.commit()
    db.refresh(trade)

    result = _trade_to_out(trade)
    result["recalculated_months"] = recalculated
    result["affected_from"] = from_date.strftime("%Y-%m")
    return result


@router.delete("/{trade_id}", status_code=204)
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(EquityTrade).filter(EquityTrade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Operación no encontrada")

    instrument_id = trade.instrument_id
    trade_date = trade.date

    db.delete(trade)
    db.flush()

    recalculate_equity_positions(instrument_id, trade_date, db)
    db.commit()
