from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.expenses.db import get_exp_db
from app.expenses.models import ExpAccount

router = APIRouter(prefix="/api/expenses/accounts", tags=["expenses"])


def _out(a: ExpAccount, with_identifiers: bool = False) -> dict:
    d = {
        "id": a.id, "name": a.name, "institution": a.institution, "country": a.country,
        "kind": a.kind, "currency": a.currency, "parser_key": a.parser_key,
        "paid_from_account_id": a.paid_from_account_id, "default_entity_id": a.default_entity_id,
        "has_statements": a.has_statements, "active": a.active,
    }
    if with_identifiers:  # sensible: sólo en el detalle de configuración
        d["owner_identifiers"] = a.owner_identifiers or []
    return d


class AccountIn(BaseModel):
    name: str
    institution: str
    country: str
    kind: str
    currency: str
    parser_key: Optional[str] = None
    owner_identifiers: list[str] = []
    paid_from_account_id: Optional[int] = None
    default_entity_id: Optional[int] = None
    has_statements: bool = True


class AccountPatch(BaseModel):
    name: Optional[str] = None
    parser_key: Optional[str] = None
    owner_identifiers: Optional[list[str]] = None
    paid_from_account_id: Optional[int] = None
    default_entity_id: Optional[int] = None
    has_statements: Optional[bool] = None
    active: Optional[bool] = None


@router.get("")
def list_accounts(db: Session = Depends(get_exp_db)):
    return [_out(a) for a in db.query(ExpAccount).order_by(ExpAccount.id)]


@router.get("/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_exp_db)):
    a = db.get(ExpAccount, account_id)
    if a is None:
        raise HTTPException(404, "Cuenta inexistente")
    return _out(a, with_identifiers=True)


@router.post("", status_code=201)
def create_account(body: AccountIn, db: Session = Depends(get_exp_db)):
    if body.country not in ("AR", "BR") or body.kind not in ("bank", "wallet", "credit_card"):
        raise HTTPException(422, "country/kind inválido")
    a = ExpAccount(**body.model_dump())
    db.add(a); db.commit()
    return _out(a, with_identifiers=True)


@router.patch("/{account_id}")
def patch_account(account_id: int, body: AccountPatch, db: Session = Depends(get_exp_db)):
    a = db.get(ExpAccount, account_id)
    if a is None:
        raise HTTPException(404, "Cuenta inexistente")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    return _out(a, with_identifiers=True)
