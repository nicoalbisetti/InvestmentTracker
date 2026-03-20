from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class TransactionCreate(BaseModel):
    instrument_id: int
    date: date
    type: str  # aplicacion, rescate, provento, outro
    amount_brl: Optional[float] = None
    amount_usd: Optional[float] = None
    notes: Optional[str] = None


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    type: Optional[str] = None
    amount_brl: Optional[float] = None
    amount_usd: Optional[float] = None
    notes: Optional[str] = None


class TransactionOut(TransactionCreate):
    id: int
    created_at: datetime
    instrument_name: Optional[str] = None
    instrument_custodian: Optional[str] = None

    model_config = {"from_attributes": True}
