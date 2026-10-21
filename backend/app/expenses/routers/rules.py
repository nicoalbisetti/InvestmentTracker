import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.expenses.db import get_exp_db
from app.expenses.models import ExpRule
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
        "set_category_id", "set_entity_id", "set_merchant", "active", "origin")}


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
