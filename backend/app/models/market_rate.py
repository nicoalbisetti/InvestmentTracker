from sqlalchemy import Column, String, Float, UniqueConstraint
from app.database import Base


class MarketRate(Base):
    __tablename__ = "market_rates"

    # date = "YYYY-MM", series = "cdi" | "ipca"
    date = Column(String(7), primary_key=True)
    series = Column(String(10), primary_key=True)
    rate = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("date", "series", name="uq_market_rate"),
    )
