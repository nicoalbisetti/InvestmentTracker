from sqlalchemy import Column, Integer, Float, Date, UniqueConstraint
from app.database import Base


class AnnualSummary(Base):
    __tablename__ = "annual_summaries"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, unique=True, index=True)
    year_date = Column(Date, nullable=True)
    total = Column(Float, nullable=True)
    diff = Column(Float, nullable=True)
    gain = Column(Float, nullable=True)
    net_flow = Column(Float, nullable=True)  # Aplicaciones/Rescates
