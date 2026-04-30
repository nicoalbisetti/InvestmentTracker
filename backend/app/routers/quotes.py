from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.database import get_db
from app.models.quote import Quote

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


@router.get("/lookup")
def lookup_quote(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    """Return the USD/BRL rate stored in Quote for a given month."""
    try:
        year, mon = int(month[:4]), int(month[5:7])
        target = date(year, mon, 1)
    except (ValueError, IndexError):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="month debe ser YYYY-MM")
    q = db.query(Quote).filter(Quote.date == target).first()
    rate = q.usd_brl if (q and q.usd_brl) else None
    return {"month": month, "rate": rate, "found": rate is not None}


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
