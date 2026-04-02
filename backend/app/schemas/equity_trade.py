from pydantic import BaseModel, field_validator
from typing import Literal, Optional
from datetime import date, datetime


class EquityTradeCreate(BaseModel):
    instrument_id: int
    date: date
    trade_type: Literal["compra", "venta"]
    quantity: float
    price: float
    notes: Optional[str] = None

    @field_validator("quantity", "price")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Debe ser mayor a 0")
        return v


class EquityTradeUpdate(BaseModel):
    date: Optional[date] = None
    trade_type: Optional[Literal["compra", "venta"]] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    notes: Optional[str] = None


class EquityTradeOut(BaseModel):
    id: int
    instrument_id: int
    date: date
    trade_type: str
    quantity: float
    price: float
    amount_brl: Optional[float]
    notes: Optional[str]
    created_at: datetime
    instrument_name: str
    instrument_ticker: Optional[str]

    model_config = {"from_attributes": True}


class EquityTradeSummary(BaseModel):
    instrument_id: int
    instrument_name: str
    instrument_ticker: Optional[str]
    total_compras_qty: float
    total_ventas_qty: float
    qty_actual: float
    avg_price_compra: Optional[float]
    ultimo_precio: Optional[float]
    pl_no_realizado: Optional[float]
    pl_no_realizado_pct: Optional[float]
