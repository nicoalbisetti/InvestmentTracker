from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Date

from app.expenses.db import ExpBase


class ExpLink(ExpBase):
    """Vínculos HACIA inversiones/proventos (sin FK por diseño: otra base de datos).

    Los vínculos internos (par de transferencias, pago de fatura) viven en columnas de
    exp_transactions. target_label/date/amount son un snapshot para detectar deriva.
    """
    __tablename__ = "exp_links"

    id = Column(Integer, primary_key=True)
    exp_transaction_id = Column(Integer, ForeignKey("exp_transactions.id"), nullable=False, index=True)
    target_type = Column(String, nullable=False)  # investment_transaction | provento_item
    target_id = Column(Integer, nullable=False)
    link_type = Column(String, nullable=False)    # investment | provento
    amount_allocated_brl = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="suggested")  # suggested | confirmed | rejected
    score = Column(Float, nullable=True)
    target_date = Column(Date, nullable=True)
    target_amount = Column(Float, nullable=True)
    target_label = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
