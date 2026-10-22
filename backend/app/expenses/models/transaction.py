from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)

from app.expenses.db import ExpBase

KINDS = (
    "expense", "refund", "income", "own_transfer", "card_payment",
    "investment_contribution", "investment_withdrawal", "provento",
    "fx_conversion", "unknown",
)
CLASSIFICATION_SOURCES = ("own_account", "rule", "manual", "default")


class ExpTransaction(ExpBase):
    __tablename__ = "exp_transactions"
    __table_args__ = (
        Index("ix_exp_tx_date", "date"),
        Index("ix_exp_tx_account_date", "account_id", "date"),
    )

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("exp_accounts.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("exp_import_batches.id"), nullable=True, index=True)
    date = Column(Date, nullable=False)                 # imputación (vencimiento en tarjetas)
    purchase_date = Column(Date, nullable=True)
    statement_period = Column(String, nullable=True)    # YYYY-MM
    description_raw = Column(Text, nullable=False)
    counterparty = Column(String, nullable=True)
    merchant_normalized = Column(String, nullable=True)
    external_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)              # con signo; negativo = sale dinero
    currency = Column(String, nullable=False)
    fx_usd_brl = Column(Float, nullable=True)
    fx_ars_usd = Column(Float, nullable=True)
    fx_estimated = Column(Boolean, nullable=False, default=False)
    amount_brl = Column(Float, nullable=True)
    amount_usd = Column(Float, nullable=True)
    kind = Column(String, nullable=False, default="unknown")
    category_id = Column(Integer, ForeignKey("exp_categories.id"), nullable=True)
    entity_id = Column(Integer, ForeignKey("exp_entities.id"), nullable=True)
    installment_number = Column(Integer, nullable=True)
    installment_total = Column(Integer, nullable=True)
    classification_source = Column(String, nullable=False, default="default")
    rule_id = Column(Integer, ForeignKey("exp_rules.id"), nullable=True)
    needs_review = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    # Vínculos internos como columnas directas (ver revisión §3.2)
    transfer_group_id = Column(Integer, nullable=True, index=True)  # par own_transfer
    # cuenta propia a la que va/de la que viene una transferencia (aunque no se importe): guía el pareo y la cola
    counterparty_account_id = Column(Integer, ForeignKey("exp_accounts.id"), nullable=True)
    exclude_from_audit = Column(Boolean, nullable=False, default=False)  # aporte que no se rastrea en Inversiones (p. ej. cripto)
    statement_batch_id = Column(Integer, ForeignKey("exp_import_batches.id"), nullable=True)  # card_payment -> resumen
    dedup_hash = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
