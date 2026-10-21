from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.expenses.db import get_exp_db
from app.expenses.models import ExpAccount

router = APIRouter(prefix="/api/expenses/accounts", tags=["expenses"])


@router.get("")
def list_accounts(db: Session = Depends(get_exp_db)):
    # owner_identifiers es sensible: no se expone en el listado.
    return [
        {
            "id": a.id, "name": a.name, "institution": a.institution, "country": a.country,
            "kind": a.kind, "currency": a.currency, "parser_key": a.parser_key,
            "paid_from_account_id": a.paid_from_account_id, "has_statements": a.has_statements,
            "active": a.active,
        }
        for a in db.query(ExpAccount).order_by(ExpAccount.id)
    ]
