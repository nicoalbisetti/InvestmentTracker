from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from datetime import datetime
from app.database import Base


class InstrumentCodeMapping(Base):
    """Persistent mapping from Excel codigo to instrument_id for future imports."""
    __tablename__ = "instrument_code_mappings"

    id = Column(Integer, primary_key=True, index=True)
    codigo_excel = Column(String, nullable=False, unique=True, index=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
