from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ticker = Column(String, nullable=True, index=True)  # Unique code/ISIN from Excel
    custodian = Column(String, nullable=False)
    type = Column(String, default="outro")  # renta_fija, accion, fii, fundo, previdencia, prestamos, saving, outro
    location = Column(String, default="brasil")  # brasil | exterior
    currency = Column(String, default="BRL")  # BRL, USD
    maturity_date = Column(Date, nullable=True)
    issue_date = Column(Date, nullable=True)       # Data de Emissão
    index_type = Column(String, nullable=True)      # PREFIXADO / IPCA / DI / SELIC
    in_liquidation = Column(Boolean, default=False)  # EM LIQUIDACAO EXTRAJUDICIAL
    pays_dividends = Column(Boolean, default=False)  # Paga dividendos / proventos periódicos
    asset_class = Column(String, nullable=True)    # CDB / CRI / CRA / DEB / LCA / LCI / LIG / TD / FUNDO_CREDITO
    liquidity = Column(String, nullable=True)  # D+2, D+30, etc.
    status = Column(String, default="activo")  # activo, cerrado, sin_datos
    created_at = Column(DateTime, default=datetime.utcnow)

    # Fields updated from Ranking sheet
    rank_1m = Column(Integer, nullable=True)
    rank_3m = Column(Integer, nullable=True)
    rank_6m = Column(Integer, nullable=True)
    rank_12m = Column(Integer, nullable=True)
    return_1m = Column(Float, nullable=True)
    return_3m = Column(Float, nullable=True)
    return_6m = Column(Float, nullable=True)
    return_12m = Column(Float, nullable=True)
    current_balance_brl = Column(Float, nullable=True)
    portfolio_pct = Column(Float, nullable=True)

    positions = relationship("MonthlyPosition", back_populates="instrument", cascade="all, delete-orphan")
    proventos = relationship("Provento", back_populates="instrument", cascade="all, delete-orphan")
    forecasts = relationship("ProventoForecast", back_populates="instrument", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="instrument", cascade="all, delete-orphan")
    provento_items = relationship("ProvéntoItem", back_populates="instrument", cascade="all, delete-orphan")
    equity_trades = relationship("EquityTrade", back_populates="instrument", cascade="all, delete-orphan")
