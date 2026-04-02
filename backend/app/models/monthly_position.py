from sqlalchemy import Column, Integer, Float, Date, String, ForeignKey, UniqueConstraint
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
    quantity = Column(Float, nullable=True)          # Quantidade Disponível
    unit_price = Column(Float, nullable=True)        # Preço Atualizado MTM o CURVA
    custodian_override = Column(String, nullable=True)  # For same-instrument cross-custodian positions
    capital_invested = Column(Float, nullable=True)  # Valor Aplicado (Tesouro Direto)

    __table_args__ = (UniqueConstraint("instrument_id", "date", "custodian_override", name="uq_instrument_date_custodian"),)

    instrument = relationship("Instrument", back_populates="positions")
