from sqlalchemy import Column, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class ProventoForecast(Base):
    __tablename__ = "provento_forecast"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    amount = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("instrument_id", "year", "month", name="uq_forecast_instrument_year_month"),)

    instrument = relationship("Instrument", back_populates="forecasts")
