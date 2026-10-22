"""Conversión de proventos entre la moneda del instrumento y BRL."""
from datetime import date
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.quote import Quote


def get_month_usd_rate(db: Session, year: int, month: int) -> Optional[float]:
    """Cotización USD/BRL del mes: Quote del mes → snapshot del mes → última Quote anterior."""
    month_start = date(year, month, 1)
    q = db.query(Quote).filter(Quote.date == month_start, Quote.usd_brl.isnot(None)).first()
    if q:
        return q.usd_brl
    snap = (
        db.query(PortfolioSnapshot)
        .filter(
            func.strftime("%Y-%m", PortfolioSnapshot.date) == month_start.strftime("%Y-%m"),
            PortfolioSnapshot.usd_rate.isnot(None),
        )
        .first()
    )
    if snap:
        return snap.usd_rate
    q = (
        db.query(Quote)
        .filter(Quote.date <= month_start, Quote.usd_brl.isnot(None))
        .order_by(Quote.date.desc())
        .first()
    )
    return q.usd_brl if q else None


def to_brl(db: Session, amount: float, currency: Optional[str], year: int, month: int):
    """Devuelve (amount_brl, amount_native, rate). amount_native es None para instrumentos BRL.
    Lanza ValueError si el instrumento es USD y no hay cotización disponible."""
    if currency != "USD":
        return float(amount), None, None
    rate = get_month_usd_rate(db, year, month)
    if not rate:
        raise ValueError("No hay cotización USD/BRL disponible para convertir")
    return round(float(amount) * rate, 2), float(amount), rate
