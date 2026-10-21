from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.expenses.db import get_exp_db
from app.expenses.models import ExpCategory, ExpEntity, ExpTransaction
from app.expenses.services import fx, linking, review, summary as summary_svc

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("/summary")
def get_summary(
    date_from: Optional[str] = Query(None, alias="from"), date_to: Optional[str] = Query(None, alias="to"),
    entity: Optional[str] = None, country: Optional[str] = None, currency: str = "BRL",
    db: Session = Depends(get_exp_db),
):
    """from/to en YYYY-MM."""
    if currency not in ("BRL", "USD", "native"):
        raise HTTPException(422, "currency inválida")
    return summary_svc.summary(db, date_from, date_to, entity, country, currency)


@router.get("/review-queue")
def get_review_queue(db: Session = Depends(get_exp_db)):
    return review.review_queue(db)


@router.get("/coverage")
def get_coverage(db: Session = Depends(get_exp_db)):
    return summary_svc.coverage(db)


class PairBody(BaseModel):
    out_id: int
    in_id: int


@router.post("/links/rebuild")
def rebuild_links(db: Session = Depends(get_exp_db), inv: Session = Depends(linking.get_inv_db)):
    """Recalcula vínculos internos y sugiere vínculos con inversiones/proventos (nunca confirma estos últimos)."""
    return {**linking.rebuild(db), **linking.rebuild_investments(db, inv)}


@router.get("/links/suggestions")
def list_link_suggestions(status: str = "suggested", db: Session = Depends(get_exp_db)):
    if status not in ("suggested", "confirmed", "rejected"):
        raise HTTPException(422, "status inválido")
    return linking.suggestions(db, status)


@router.post("/links/{link_id}/confirm")
def confirm_link(link_id: int, db: Session = Depends(get_exp_db)):
    if linking.set_link_status(db, link_id, "confirmed") is None:
        raise HTTPException(404, "Vínculo inexistente")
    return {"ok": True}


@router.post("/links/{link_id}/reject")
def reject_link(link_id: int, db: Session = Depends(get_exp_db)):
    if linking.set_link_status(db, link_id, "rejected") is None:
        raise HTTPException(404, "Vínculo inexistente")
    return {"ok": True}


@router.get("/audit/investments")
def audit_investments(date_from: Optional[date] = Query(None, alias="from"), date_to: Optional[date] = Query(None, alias="to"),
                      db: Session = Depends(get_exp_db), inv: Session = Depends(linking.get_inv_db)):
    """Auditoría de sólo lectura sobre inversiones: nunca modifica las tablas de inversiones."""
    return linking.audit_investments(db, inv, date_from, date_to)


@router.post("/links/pairs")
def confirm_pair(body: PairBody, db: Session = Depends(get_exp_db)):
    a, b = db.get(ExpTransaction, body.out_id), db.get(ExpTransaction, body.in_id)
    if not a or not b or a.kind != b.kind or a.kind not in linking.PAIR_KINDS or a.account_id == b.account_id:
        raise HTTPException(422, "Par inválido")
    gid = min(a.id, b.id)
    a.transfer_group_id = b.transfer_group_id = gid
    db.commit()
    return {"group_id": gid}


@router.delete("/links/pairs/{group_id}")
def reject_pair(group_id: int, db: Session = Depends(get_exp_db)):
    n = db.query(ExpTransaction).filter_by(transfer_group_id=group_id).update({"transfer_group_id": None})
    db.commit()
    return {"unlinked": n}


@router.post("/fx/recompute")
def recompute_fx(date_from: date = Query(..., alias="from"), date_to: date = Query(..., alias="to"), db: Session = Depends(get_exp_db)):
    """Recalcula amount_brl/usd de los movimientos del rango con los tipos de cambio vigentes
    (incluye cargas manuales). Sólo toca ese rango."""
    txs = db.query(ExpTransaction).filter(ExpTransaction.date >= date_from, ExpTransaction.date <= date_to).all()
    for t in txs:
        c = fx.convert(db, t.amount, t.currency, t.date)
        t.amount_brl, t.amount_usd, t.fx_usd_brl, t.fx_ars_usd, t.fx_estimated = (
            c.amount_brl, c.amount_usd, c.fx_usd_brl, c.fx_ars_usd, c.estimated)
    db.commit()
    return {"recomputed": len(txs)}


@router.get("/categories")
def list_categories(db: Session = Depends(get_exp_db)):
    return [{"id": c.id, "name": c.name, "is_system": c.is_system, "active": c.active}
            for c in db.query(ExpCategory).order_by(ExpCategory.name)]


class CategoryIn(BaseModel):
    name: str


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, db: Session = Depends(get_exp_db)):
    if db.query(ExpCategory).filter_by(name=body.name).first():
        raise HTTPException(409, "Ya existe")
    c = ExpCategory(name=body.name, is_system=False)
    db.add(c); db.commit()
    return {"id": c.id, "name": c.name}


@router.get("/entities")
def list_entities(db: Session = Depends(get_exp_db)):
    return [{"id": e.id, "code": e.code, "name": e.name, "active": e.active} for e in db.query(ExpEntity)]
