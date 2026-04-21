from sqlalchemy import Column, Integer, Float, Date, UniqueConstraint
from app.database import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True, unique=True)
    total_brl = Column(Float, nullable=True)
    total_without_b3 = Column(Float, nullable=True)
    total_usd = Column(Float, nullable=True)
    usd_rate = Column(Float, nullable=True)
    monthly_change_pct = Column(Float, nullable=True)

    # By custodian
    hsbc_total = Column(Float, nullable=True)
    bradesco_total = Column(Float, nullable=True)
    xp_br_total = Column(Float, nullable=True)
    xp_us_total = Column(Float, nullable=True)
    santander_total = Column(Float, nullable=True)
    inter_total = Column(Float, nullable=True)
    brasil_total = Column(Float, nullable=True)
    fgts = Column(Float, nullable=True)
    prev = Column(Float, nullable=True)
    usa_total = Column(Float, nullable=True)
