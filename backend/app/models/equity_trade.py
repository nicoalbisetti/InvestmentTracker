from sqlalchemy import Column, Integer, Float, Date, DateTime, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class EquityTrade(Base):
    __tablename__ = "equity_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    trade_type = Column(String(10), nullable=False)  # "compra" | "venta"
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    amount_brl = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    instrument = relationship("Instrument", back_populates="equity_trades")
