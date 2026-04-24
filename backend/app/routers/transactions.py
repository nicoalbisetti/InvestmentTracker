from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date
from dateutil.relativedelta import relativedelta
from app.database import get_db
from app.models.transaction import Transaction
from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from app.schemas.transaction import TransactionCreate, TransactionUpdate, TransactionOut
from app.services.snapshot_sync import sync_snapshot_for_date

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _recompute_positions(db: Session, instrument_id: int, from_date: date):
    """Recompute monthly position balances from from_date onwards based on transactions."""
    month_start = from_date.replace(day=1)

    # Find the balance at the end of the immediately preceding month
    prev_pos = (
        db.query(MonthlyPosition)
        .filter(
            MonthlyPosition.instrument_id == instrument_id,
            MonthlyPosition.date < month_start,
        )
        .order_by(MonthlyPosition.date.desc())
        .first()
    )
    prev_brl = (prev_pos.balance_brl or 0.0) if prev_pos else 0.0
    prev_usd = (prev_pos.balance_usd or 0.0) if prev_pos else 0.0

    # Get all months that have a position row from month_start onwards
    future_positions = (
        db.query(MonthlyPosition)
        .filter(
            MonthlyPosition.instrument_id == instrument_id,
            MonthlyPosition.date >= month_start,
        )
        .order_by(MonthlyPosition.date.asc())
        .all()
    )

    # Ensure current month has a position row
    today_month = date.today().replace(day=1)
    months_with_rows = {p.date for p in future_positions}
    if month_start not in months_with_rows:
        # Get usd_rate from the most recent position
        last_pos = (
            db.query(MonthlyPosition)
            .filter(MonthlyPosition.instrument_id == instrument_id)
            .order_by(MonthlyPosition.date.desc())
            .first()
        )
        new_pos = MonthlyPosition(
            instrument_id=instrument_id,
            date=month_start,
            balance_brl=0.0,
            balance_usd=0.0,
            usd_rate=last_pos.usd_rate if last_pos else None,
        )
        db.add(new_pos)
        db.flush()
        future_positions = (
            db.query(MonthlyPosition)
            .filter(
                MonthlyPosition.instrument_id == instrument_id,
                MonthlyPosition.date >= month_start,
            )
            .order_by(MonthlyPosition.date.asc())
            .all()
        )

    running_brl = prev_brl
    running_usd = prev_usd

    for pos in future_positions:
        m = pos.date
        # Sum transactions for this month
        txns = (
            db.query(Transaction)
            .filter(
                Transaction.instrument_id == instrument_id,
                func.strftime('%Y-%m', Transaction.date) == m.strftime('%Y-%m'),
            )
            .all()
        )
        net_brl = sum(
            (t.amount_brl or 0) * (1 if t.type == 'aplicacion' else -1)
            for t in txns if t.type in ('aplicacion', 'rescate')
        )
        net_usd = sum(
            (t.amount_usd or 0) * (1 if t.type == 'aplicacion' else -1)
            for t in txns if t.type in ('aplicacion', 'rescate') and t.amount_usd
        )
        running_brl = running_brl + net_brl
        running_usd = running_usd + net_usd
        pos.balance_brl = max(running_brl, 0.0)
        pos.balance_usd = max(running_usd, 0.0) if running_usd else pos.balance_usd
        
        db.flush()
        sync_snapshot_for_date(db, m)

    db.commit()


@router.get("")
def get_transactions(
    instrument_id: Optional[int] = None,
    type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    custodian: Optional[str] = Query(None),
    month_year: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).order_by(Transaction.date.desc())
    if instrument_id:
        query = query.filter(Transaction.instrument_id == instrument_id)
    if type:
        query = query.filter(Transaction.type == type)
    if date_from:
        query = query.filter(Transaction.date >= date_from)
    if date_to:
        query = query.filter(Transaction.date <= date_to)
    if custodian:
        query = query.join(Instrument, Transaction.instrument_id == Instrument.id)
        query = query.filter(Instrument.custodian == custodian)
    if month_year:
        query = query.filter(func.strftime('%Y-%m', Transaction.date) == month_year)

    total = query.count()
    txns = query.offset((page - 1) * limit).limit(limit).all()

    items = []
    for t in txns:
        inst = db.query(Instrument).filter_by(id=t.instrument_id).first()
        items.append({
            "id": t.id,
            "instrument_id": t.instrument_id,
            "instrument_name": inst.name if inst else None,
            "instrument_custodian": inst.custodian if inst else None,
            "date": t.date.isoformat(),
            "type": t.type,
            "amount_brl": t.amount_brl,
            "amount_usd": t.amount_usd,
            "notes": t.notes,
            "created_at": t.created_at.isoformat(),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("", status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    inst = db.query(Instrument).filter_by(id=payload.instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")

    txn = Transaction(**payload.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)
    _recompute_positions(db, txn.instrument_id, txn.date)
    return {"id": txn.id, "message": "Transaccion creada"}


@router.put("/{txn_id}")
def update_transaction(txn_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter_by(id=txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaccion no encontrada")

    affected_date = payload.date or txn.date
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(txn, k, v)
    db.commit()
    _recompute_positions(db, txn.instrument_id, affected_date)
    return {"message": "Transaccion actualizada"}


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter_by(id=txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaccion no encontrada")
    instrument_id, txn_date = txn.instrument_id, txn.date
    db.delete(txn)
    db.commit()
    _recompute_positions(db, instrument_id, txn_date)
