from sqlalchemy import Column, Integer, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class MonthlyPosition(Base):
    __tablename__ = "monthly_positions"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)  # Normalized to first of month
    balance_brl = Column(Float, nullable=True)
    balance_usd = Column(Float, nullable=True)
    usd_rate = Column(Float, nullable=True)
    applications = Column(Float, nullable=True)
    redemptions = Column(Float, nullable=True)
    calculated_balance = Column(Float, nullable=True)
    previous_balance = Column(Float, nullable=True)
    gain = Column(Float, nullable=True)
    gain_pct = Column(Float, nullable=True)
    proventos = Column(Float, nullable=True)
    avg_price = Column(Float, nullable=True)

    __table_args__ = (UniqueConstraint("instrument_id", "date", name="uq_instrument_date"),)

    instrument = relationship("Instrument", back_populates="positions")
