from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String

from app.expenses.db import ExpBase


class ExpAccount(ExpBase):
    __tablename__ = "exp_accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    institution = Column(String, nullable=False)
    country = Column(String, nullable=False)    # AR | BR
    kind = Column(String, nullable=False)       # bank | wallet | credit_card
    currency = Column(String, nullable=False)   # ARS | BRL | USD (la principal)
    parser_key = Column(String, nullable=True)
    # Identificadores de cuentas PROPIAS (nombres, documentos, CBU/CVU). Datos sensibles:
    # nunca loguear ni devolver fuera del endpoint de configuración.
    owner_identifiers = Column(JSON, nullable=False, default=list)
    paid_from_account_id = Column(Integer, ForeignKey("exp_accounts.id"), nullable=True)
    default_entity_id = Column(Integer, ForeignKey("exp_entities.id"), nullable=True)
    has_statements = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
