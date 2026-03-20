from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from datetime import datetime
from app.database import Base


class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    imported_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="success")  # success, partial, failed
    records_instruments = Column(Integer, default=0)
    records_positions = Column(Integer, default=0)
    records_snapshots = Column(Integer, default=0)
    records_annual = Column(Integer, default=0)
    records_proventos = Column(Integer, default=0)
    records_quotes = Column(Integer, default=0)
    records_ranking = Column(Integer, default=0)
    warnings = Column(JSON, default=list)
    errors = Column(JSON, default=list)
