from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.quote import Quote

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


@router.get("")
def get_quotes(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Quote).order_by(Quote.date.desc())
    if date_from:
        query = query.filter(Quote.date >= date_from)
    if date_to:
        query = query.filter(Quote.date <= date_to)
    quotes = query.limit(120).all()
    return [
        {"date": q.date.isoformat(), "usd_brl": q.usd_brl, "bvmf3_price": q.bvmf3_price}
        for q in quotes
    ]


@router.post("", status_code=201)
def create_quote(
    quote_date: date,
    usd_brl: float,
    bvmf3_price: Optional[float] = None,
    db: Session = Depends(get_db),
):
    normalized = date(quote_date.year, quote_date.month, 1)
    existing = db.query(Quote).filter_by(date=normalized).first()
    if existing:
        existing.usd_brl = usd_brl
        existing.bvmf3_price = bvmf3_price
    else:
        db.add(Quote(date=normalized, usd_brl=usd_brl, bvmf3_price=bvmf3_price))
    db.commit()
    return {"message": "Cotizacion guardada", "date": normalized.isoformat()}
