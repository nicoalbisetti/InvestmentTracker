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


class InstrumentCreate(BaseModel):
    name: str
    custodian: str
    type: str = "outro"
    currency: str = "BRL"
    status: str = "activo"
    location: str = "brasil"
    liquidity: Optional[str] = None
    maturity_date: Optional[date] = None
    index_type: Optional[str] = None
    asset_class: Optional[str] = None
    balance_brl: Optional[float] = None
    initial_period: Optional[str] = None  # "YYYY-MM"


class InstrumentUpdate(BaseModel):
    name: Optional[str] = None
    custodian: Optional[str] = None
    ticker: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    currency: Optional[str] = None
    maturity_date: Optional[date] = None
    issue_date: Optional[date] = None
    index_type: Optional[str] = None
    asset_class: Optional[str] = None
    liquidity: Optional[str] = None
    status: Optional[str] = None
    in_liquidation: Optional[bool] = None
    pays_dividends: Optional[bool] = None


class InstrumentOut(InstrumentBase):
    id: int
    location: Optional[str] = None
    ticker: Optional[str] = None
    issue_date: Optional[date] = None
    index_type: Optional[str] = None
    asset_class: Optional[str] = None
    in_liquidation: Optional[bool] = None
    pays_dividends: Optional[bool] = None
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
