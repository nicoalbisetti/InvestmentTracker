from sqlalchemy import Column, Integer, Float, Date
from app.database import Base


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    usd_brl = Column(Float, nullable=True)
    bvmf3_price = Column(Float, nullable=True)
