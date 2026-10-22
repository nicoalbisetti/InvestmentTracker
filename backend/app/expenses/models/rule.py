from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.expenses.db import ExpBase


class ExpRule(ExpBase):
    __tablename__ = "exp_rules"

    id = Column(Integer, primary_key=True)
    priority = Column(Integer, nullable=False, default=100)  # menor = primero
    account_id = Column(Integer, ForeignKey("exp_accounts.id"), nullable=True)
    field = Column(String, nullable=False, default="description_raw")  # description_raw | counterparty | merchant_normalized
    pattern = Column(String, nullable=False)                 # regex, case-insensitive
    amount_sign = Column(String, nullable=False, default="any")  # any | positive | negative
    set_kind = Column(String, nullable=False)
    set_category_id = Column(Integer, ForeignKey("exp_categories.id"), nullable=True)
    set_entity_id = Column(Integer, ForeignKey("exp_entities.id"), nullable=True)
    set_merchant = Column(String, nullable=True)
    set_needs_review = Column(Boolean, nullable=False, default=False)  # la regla clasifica pero deja la fila en revisión
    set_counterparty_account_id = Column(Integer, ForeignKey("exp_accounts.id"), nullable=True)
    set_exclude_from_audit = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True)
    origin = Column(String, nullable=False, default="manual")  # seed | manual
    seed_key = Column(String, nullable=True, unique=True)      # clave estable para re-seed idempotente
    created_at = Column(DateTime, default=datetime.utcnow)
