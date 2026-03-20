from sqlalchemy import Column, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Provento(Base):
    __tablename__ = "proventos"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=True)  # 1-12, NULL for annual totals
    amount = Column(Float, nullable=True)

    __table_args__ = (UniqueConstraint("instrument_id", "year", "month", name="uq_prov_instrument_year_month"),)

    instrument = relationship("Instrument", back_populates="proventos")
