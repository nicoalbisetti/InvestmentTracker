from pydantic import BaseModel
from typing import Optional
from datetime import date


class InstrumentBase(BaseModel):
    name: str
    custodian: str
    type: str = "outro"
    currency: str = "BRL"
    maturity_date: Optional[date] = None
    liquidity: Optional[str] = None
    status: str = "activo"


class InstrumentCreate(InstrumentBase):
    pass


class InstrumentUpdate(BaseModel):
    type: Optional[str] = None
    currency: Optional[str] = None
    maturity_date: Optional[date] = None
    liquidity: Optional[str] = None
    status: Optional[str] = None


class InstrumentOut(InstrumentBase):
    id: int
    rank_1m: Optional[int] = None
    rank_3m: Optional[int] = None
    rank_6m: Optional[int] = None
    rank_12m: Optional[int] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_12m: Optional[float] = None
    current_balance_brl: Optional[float] = None
    portfolio_pct: Optional[float] = None

    model_config = {"from_attributes": True}
