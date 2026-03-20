from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.transaction import Transaction
from app.models.instrument import Instrument
from app.schemas.transaction import TransactionCreate, TransactionUpdate, TransactionOut

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("")
def get_transactions(
    instrument_id: Optional[int] = None,
    type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
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
    return {"id": txn.id, "message": "Transaccion creada"}


@router.put("/{txn_id}")
def update_transaction(txn_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter_by(id=txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaccion no encontrada")

    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(txn, k, v)
    db.commit()
    return {"message": "Transaccion actualizada"}


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter_by(id=txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaccion no encontrada")
    db.delete(txn)
    db.commit()
