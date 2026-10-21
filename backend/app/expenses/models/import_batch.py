from datetime import datetime

from sqlalchemy import JSON, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.expenses.db import ExpBase


class ExpImportBatch(ExpBase):
    __tablename__ = "exp_import_batches"
    __table_args__ = (UniqueConstraint("account_id", "file_hash", name="uq_exp_batch_account_hash"),)

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("exp_accounts.id"), nullable=False, index=True)
    # Etiqueta saneada: NO persistir el nombre original (puede contener nº de cuenta).
    file_label = Column(String, nullable=True)
    file_hash = Column(String, nullable=False)  # sha256
    parser_key = Column(String, nullable=False)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    statement_due_date = Column(Date, nullable=True)    # tarjetas
    statement_period = Column(String, nullable=True)    # YYYY-MM, tarjetas
    statement_totals = Column(JSON, nullable=True)      # {"ARS": 123.45, "USD": 3.07}
    validation = Column(JSON, nullable=True)            # checks y resultado (sin identificadores)
    preview_rows = Column(JSON, nullable=True)          # staging mientras status=preview
    rows_total = Column(Integer, default=0)
    rows_new = Column(Integer, default=0)
    rows_duplicate = Column(Integer, default=0)
    status = Column(String, nullable=False, default="preview")  # preview | confirmed | discarded
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
