import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.expenses.db import get_exp_db
from app.expenses.models import ExpRule, ExpTransaction
from app.expenses.models.transaction import KINDS
from app.expenses.services import rules as rules_svc

router = APIRouter(prefix="/api/expenses/rules", tags=["expenses"])


class RuleIn(BaseModel):
    pattern: str
    set_kind: str
    priority: int = 100
    field: str = "merchant_normalized"
    amount_sign: str = "any"
    account_id: Optional[int] = None
    set_category_id: Optional[int] = None
    set_entity_id: Optional[int] = None
    set_merchant: Optional[str] = None
    set_needs_review: bool = False
    set_counterparty_account_id: Optional[int] = None
    set_exclude_from_audit: bool = False
    apply_to_pending: bool = False


def _validate(body: RuleIn):
    if body.set_kind not in KINDS:
        raise HTTPException(422, "kind inválido")
    if body.field not in ("description_raw", "counterparty", "merchant_normalized"):
        raise HTTPException(422, "field inválido")
    if body.amount_sign not in ("any", "positive", "negative"):
        raise HTTPException(422, "amount_sign inválido")
    try:
        re.compile(body.pattern)
    except re.error as e:
        raise HTTPException(422, f"regex inválida: {e}")


def _out(r: ExpRule) -> dict:
    return {c: getattr(r, c) for c in (
        "id", "priority", "account_id", "field", "pattern", "amount_sign", "set_kind",
        "set_category_id", "set_entity_id", "set_merchant", "set_needs_review", "set_counterparty_account_id",
        "set_exclude_from_audit", "active", "origin")}


@router.get("")
def list_rules(db: Session = Depends(get_exp_db)):
    return [_out(r) for r in db.query(ExpRule).order_by(ExpRule.priority, ExpRule.id)]


@router.post("/preview")
def preview_rule(body: RuleIn, db: Session = Depends(get_exp_db)):
    """Impacto de una regla sobre las filas pendientes, sin guardar nada."""
    _validate(body)
    r = ExpRule(**body.model_dump(exclude={"apply_to_pending"}), origin="manual")
    hits = rules_svc.pending_matches(db, r)
    return {"count": len(hits), "sample": [{"id": t.id, "description": t.description_raw} for t in hits[:20]]}


@router.post("", status_code=201)
def create_rule(body: RuleIn, db: Session = Depends(get_exp_db)):
    _validate(body)
    r = ExpRule(**body.model_dump(exclude={"apply_to_pending"}), origin="manual")
    db.add(r); db.commit()
    applied = rules_svc.apply_rule_to_pending(db, r) if body.apply_to_pending else 0
    return {**_out(r), "applied": applied}


@router.post("/reapply")
def reapply_rules(include_rule_rows: bool = False, db: Session = Depends(get_exp_db)):
    """Pasa las filas pendientes por las reglas vigentes (útil después de editar o recargar reglas).
    include_rule_rows=true re-evalúa también las ya clasificadas por una regla (nunca las manuales)."""
    return rules_svc.reclassify_pending(db, include_rule_rows)


class RulePatch(BaseModel):
    pattern: Optional[str] = None
    set_kind: Optional[str] = None
    priority: Optional[int] = None
    field: Optional[str] = None
    amount_sign: Optional[str] = None
    account_id: Optional[int] = None
    set_category_id: Optional[int] = None
    set_entity_id: Optional[int] = None
    set_merchant: Optional[str] = None
    set_needs_review: Optional[bool] = None
    set_counterparty_account_id: Optional[int] = None
    set_exclude_from_audit: Optional[bool] = None
    active: Optional[bool] = None
    apply_to_pending: bool = False


@router.patch("/{rule_id}")
def patch_rule(rule_id: int, body: RulePatch, db: Session = Depends(get_exp_db)):
    """Edita una regla. Si era 'seed' pasa a 'manual': así recargar las semillas no pisa tus cambios."""
    r = db.get(ExpRule, rule_id)
    if r is None:
        raise HTTPException(404, "Regla inexistente")
    data = body.model_dump(exclude_unset=True, exclude={"apply_to_pending"})
    probe = RuleIn(**{**{c: getattr(r, c) for c in ("pattern", "set_kind", "field", "amount_sign")}, **{
        k: v for k, v in data.items() if k in ("pattern", "set_kind", "field", "amount_sign") and v is not None}})
    _validate(probe)
    for k, v in data.items():
        setattr(r, k, v)
    r.origin = "manual"
    db.commit()
    applied = rules_svc.apply_rule_to_pending(db, r) if body.apply_to_pending and r.active else 0
    return {**_out(r), "applied": applied}


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_exp_db)):
    r = db.get(ExpRule, rule_id)
    if r is None:
        raise HTTPException(404, "Regla inexistente")
    if r.origin == "seed":
        raise HTTPException(409, "Las reglas semilla no se borran (se volverían a cargar): desactivala")
    db.query(ExpTransaction).filter(ExpTransaction.rule_id == rule_id).update({"rule_id": None})
    db.delete(r); db.commit()
    return {"deleted": rule_id}


class Reorder(BaseModel):
    ids: list[int]


@router.post("/reorder")
def reorder_rules(body: Reorder, db: Session = Depends(get_exp_db)):
    """Define el orden de evaluación (el primero gana). `ids` debe contener TODAS las reglas. Sólo cambian de
    prioridad las que cambian de lugar; las semilla que se mueven pasan a 'manual'."""
    rules = db.query(ExpRule).order_by(ExpRule.priority, ExpRule.id).all()
    if sorted(body.ids) != sorted(r.id for r in rules):
        raise HTTPException(422, "ids debe contener todas las reglas, sin repetir")
    prios = sorted(r.priority for r in rules)
    if len(set(prios)) != len(prios):
        prios = [(i + 1) * 10 for i in range(len(rules))]
    by_id = {r.id: r for r in rules}
    moved = 0
    for pos, rid in enumerate(body.ids):
        r = by_id[rid]
        if r.priority != prios[pos]:
            r.priority = prios[pos]
            r.origin = "manual"
            moved += 1
    db.commit()
    return {"moved": moved}
