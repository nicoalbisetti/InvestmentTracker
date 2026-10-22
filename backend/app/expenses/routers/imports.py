from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.expenses.db import get_exp_db
from app.expenses.models import ExpImportBatch
from app.expenses.services import importer
from app.expenses.services.importer import ImportError_, batch_detail

router = APIRouter(prefix="/api/expenses/imports", tags=["expenses"])


def _raise(e: ImportError_):
    raise HTTPException(e.status, e.detail)


@router.post("")
async def create_import(
    file: UploadFile = File(...), account_id: Optional[int] = Form(None), due_date: Optional[date] = Form(None),
    db: Session = Depends(get_exp_db),
):
    data = await file.read()
    try:
        return importer.create_preview(db, data, file.filename or "", account_id, due_date)
    except ImportError_ as e:
        _raise(e)


class Override(BaseModel):
    index: int
    kind: Optional[str] = None
    category_id: Optional[int] = None
    entity_id: Optional[int] = None


class ConfirmBody(BaseModel):
    account_id: Optional[int] = None
    overrides: list[Override] = []
    force: bool = False


@router.post("/{batch_id}/confirm")
def confirm_import(batch_id: int, body: ConfirmBody, db: Session = Depends(get_exp_db)):
    try:
        return importer.confirm(
            db, batch_id, [o.model_dump(exclude_none=True) for o in body.overrides], body.force, body.account_id)
    except ImportError_ as e:
        _raise(e)


@router.delete("/{batch_id}")
def delete_import(batch_id: int, db: Session = Depends(get_exp_db)):
    try:
        return importer.delete_batch(db, batch_id)
    except ImportError_ as e:
        _raise(e)


@router.get("")
def list_imports(db: Session = Depends(get_exp_db)):
    return [batch_detail(b) for b in db.query(ExpImportBatch).order_by(ExpImportBatch.id.desc())]


@router.get("/{batch_id}")
def get_import(batch_id: int, db: Session = Depends(get_exp_db)):
    b = db.get(ExpImportBatch, batch_id)
    if b is None:
        raise HTTPException(404, "Lote inexistente")
    return batch_detail(b, with_rows=b.status == "preview")
