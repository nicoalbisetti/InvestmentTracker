import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.expenses.db import get_exp_db
from app.expenses.models import ExpAccount, ExpCategory, ExpEntity, ExpRule, ExpTransaction
from app.expenses.models.transaction import KINDS
from app.expenses.services import linking, rules as rules_svc
from app.expenses.services.normalize import match_key

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


def _out(t: ExpTransaction, acc: ExpAccount, cats: dict, ents: dict) -> dict:
    return {
        "id": t.id, "account_id": t.account_id, "account": acc.name, "country": acc.country,
        "date": t.date.isoformat(), "purchase_date": t.purchase_date.isoformat() if t.purchase_date else None,
        "description": t.description_raw, "counterparty": t.counterparty,
        "merchant": t.merchant_normalized, "amount": t.amount, "currency": t.currency,
        "amount_brl": t.amount_brl, "amount_usd": t.amount_usd, "kind": t.kind,
        "category_id": t.category_id, "category": cats.get(t.category_id),
        "entity_id": t.entity_id, "entity": ents.get(t.entity_id or acc.default_entity_id),
        "installment_number": t.installment_number, "installment_total": t.installment_total,
        "classification_source": t.classification_source, "needs_review": t.needs_review,
        "notes": t.notes, "paired": t.transfer_group_id is not None,
        "counterparty_account_id": t.counterparty_account_id, "exclude_from_audit": t.exclude_from_audit,
        "statement_batch_id": t.statement_batch_id, "fx_estimated": t.fx_estimated,
    }


@router.get("/transactions")
def list_transactions(
    kind: Optional[str] = None, category_id: Optional[int] = None, entity: Optional[str] = None,
    account_id: Optional[int] = None, country: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"), date_to: Optional[date] = Query(None, alias="to"), needs_review: Optional[bool] = None, q: Optional[str] = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500), db: Session = Depends(get_exp_db),
):
    query = db.query(ExpTransaction).join(ExpAccount, ExpAccount.id == ExpTransaction.account_id)
    if kind:
        query = query.filter(ExpTransaction.kind == kind)
    if category_id:
        query = query.filter(ExpTransaction.category_id == category_id)
    if account_id:
        query = query.filter(ExpTransaction.account_id == account_id)
    if country:
        query = query.filter(ExpAccount.country == country)
    if date_from:
        query = query.filter(ExpTransaction.date >= date_from)
    if date_to:
        query = query.filter(ExpTransaction.date <= date_to)
    if needs_review is not None:
        query = query.filter(ExpTransaction.needs_review.is_(needs_review))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ExpTransaction.description_raw.ilike(like), ExpTransaction.counterparty.ilike(like)))
    if entity:
        ent = db.query(ExpEntity).filter_by(code=entity).first()
        eid = ent.id if ent else -1
        query = query.filter(or_(ExpTransaction.entity_id == eid,
                                 (ExpTransaction.entity_id.is_(None)) & (ExpAccount.default_entity_id == eid)))
    total = query.count()
    rows = query.order_by(ExpTransaction.date.desc(), ExpTransaction.id.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    accounts = {a.id: a for a in db.query(ExpAccount)}
    cats = {c.id: c.name for c in db.query(ExpCategory)}
    ents = {e.id: e.code for e in db.query(ExpEntity)}
    return {"total": total, "page": page, "page_size": page_size,
            "items": [_out(t, accounts[t.account_id], cats, ents) for t in rows]}


class TxPatch(BaseModel):
    kind: Optional[str] = None
    category_id: Optional[int] = None
    entity_id: Optional[int] = None
    notes: Optional[str] = None
    counterparty_account_id: Optional[int] = None
    exclude_from_audit: Optional[bool] = None
    create_rule: bool = False


class BulkPatch(BaseModel):
    ids: list[int]
    kind: Optional[str] = None
    category_id: Optional[int] = None
    entity_id: Optional[int] = None


def _apply(db: Session, t: ExpTransaction, fields: dict) -> None:
    if fields.get("kind") is not None:
        if fields["kind"] not in KINDS:
            raise HTTPException(422, "kind inválido")
        if fields["kind"] != t.kind and t.kind in linking.PAIR_KINDS:
            linking.unlink_pair(db, t)
        t.kind = fields["kind"]
    for k in ("category_id", "entity_id"):
        if fields.get(k) is not None:
            setattr(t, k, fields[k])
    if any(fields.get(k) is not None for k in ("kind", "category_id", "entity_id")):
        t.classification_source, t.rule_id, t.needs_review = "manual", None, False


@router.patch("/transactions/{tx_id}")
def patch_transaction(tx_id: int, body: TxPatch, db: Session = Depends(get_exp_db)):
    t = db.get(ExpTransaction, tx_id)
    if t is None:
        raise HTTPException(404, "Movimiento inexistente")
    _apply(db, t, body.model_dump())
    if body.notes is not None:
        t.notes = body.notes
    if body.counterparty_account_id is not None:
        if db.get(ExpAccount, body.counterparty_account_id) is None:
            raise HTTPException(422, "cuenta de contraparte inexistente")
        t.counterparty_account_id = body.counterparty_account_id
    if body.exclude_from_audit is not None:
        t.exclude_from_audit = body.exclude_from_audit
    applied = 0
    if body.create_rule:
        key = match_key(t.merchant_normalized or t.description_raw)
        if not key:
            raise HTTPException(422, "No hay comercio para crear la regla")
        rule = ExpRule(pattern=re.escape(key), field="merchant_normalized", set_kind=t.kind,
                       amount_sign="positive" if t.amount > 0 else "negative", origin="manual",
                       set_category_id=t.category_id, set_entity_id=t.entity_id, account_id=None)
        db.add(rule); db.flush()
        db.commit()
        applied = rules_svc.apply_rule_to_pending(db, rule)
    db.commit()
    linking.rebuild(db)
    accounts = {a.id: a for a in db.query(ExpAccount)}
    cats = {c.id: c.name for c in db.query(ExpCategory)}
    ents = {e.id: e.code for e in db.query(ExpEntity)}
    db.refresh(t)
    return {**_out(t, accounts[t.account_id], cats, ents), "rule_applied_to": applied}


@router.post("/transactions/bulk")
def bulk_patch(body: BulkPatch, db: Session = Depends(get_exp_db)):
    n = 0
    for t in db.query(ExpTransaction).filter(ExpTransaction.id.in_(body.ids)):
        _apply(db, t, body.model_dump(exclude={"ids"})); n += 1
    db.commit()
    linking.rebuild(db)
    return {"updated": n}
