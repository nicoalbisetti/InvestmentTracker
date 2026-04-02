from sqlalchemy import Column, Integer, Float, String, Date, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class ProvéntoItem(Base):
    """Transaction-level provento record, imported from Excel or entered manually."""
    __tablename__ = "provento_items"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    amount_brl = Column(Float, nullable=False)
    type = Column(String(50), nullable=False)          # 'dividendo' | 'jcp' | 'amortizacion'
    notes = Column(Text, nullable=True)

    # Import fields
    quantity = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)
    custodian = Column(String(50), nullable=True)       # 'XP' | 'SANTANDER' | 'INTER'
    source = Column(String(50), nullable=True)          # 'MANUAL' | 'EXCEL_XP_SANTANDER'
    import_batch_id = Column(String(36), nullable=True, index=True)
    raw_event_type = Column(Text, nullable=True)        # original Tipo de Evento from Excel

    __table_args__ = (
        UniqueConstraint("instrument_id", "date", "type", "amount_brl", name="uq_provento_item_inst_date_type_amount"),
    )

    instrument = relationship("Instrument", back_populates="provento_items")


class ProventoImportBatch(Base):
    """Audit trail for each batch import of proventos."""
    __tablename__ = "provento_import_batches"

    id = Column(String(36), primary_key=True)           # UUID
    imported_at = Column(Text, nullable=False)           # ISO datetime string
    period_label = Column(String(100), nullable=True)    # "Febrero 2026"
    source_file = Column(Text, nullable=True)            # filename
    total_amount = Column(Float, nullable=True)
    record_count = Column(Integer, nullable=True)
    created_by = Column(String(100), nullable=True)
