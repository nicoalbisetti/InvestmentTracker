from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.expenses.db import get_exp_db
from app.expenses.models import ExpFxRate
from app.expenses.models.fx_rate import PAIR_USDARS, PAIR_USDBRL
from app.expenses.services import fx

router = APIRouter(prefix="/api/expenses/fx", tags=["expenses"])


class ManualRate(BaseModel):
    pair: str
    date: date
    rate: float


@router.put("/rates")
def put_manual_rate(body: ManualRate, db: Session = Depends(get_exp_db)):
    if body.pair not in (PAIR_USDBRL, PAIR_USDARS):
        raise HTTPException(422, "pair inválido")
    if body.rate <= 0:
        raise HTTPException(422, "rate debe ser > 0")
    fx.set_manual_rate(db, body.pair, body.date, body.rate)
    return {"ok": True}


@router.get("/rates")
def list_rates(pair: str, date_from: date, date_to: date, db: Session = Depends(get_exp_db)):
    rows = (
        db.query(ExpFxRate)
        .filter(ExpFxRate.pair == pair, ExpFxRate.date >= date_from, ExpFxRate.date <= date_to)
        .order_by(ExpFxRate.date)
    )
    return [{"date": r.date.isoformat(), "rate": r.rate, "source": r.source} for r in rows]


@router.delete("/rates")
def delete_manual_rate(pair: str, date: date, db: Session = Depends(get_exp_db)):
    """Quita una carga manual y vuelve a pedir el valor de la fuente para ese día."""
    row = db.get(ExpFxRate, (date, pair))
    if row is None or row.source != "manual":
        raise HTTPException(404, "No hay carga manual para ese día")
    db.delete(row); db.commit()
    errors = fx.refresh(db, date, date, pairs=(pair,))
    return {"restored": not errors, "errors": errors}
