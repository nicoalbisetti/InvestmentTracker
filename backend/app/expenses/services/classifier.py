"""Clasificación por fila: identificadores propios -> reglas por prioridad -> pista del parser -> default.

Nunca pisa una clasificación manual (eso lo garantiza el que aplica: ver rules.apply_rule_to_pending).
"""
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.expenses.models import ExpAccount, ExpCategory, ExpRule
from app.expenses.services.normalize import match_key, normalize_merchant, strip_accents

# Las identidades propias sólo definen "transferencia propia" en descripciones de transferencias
# (un pago de impuesto a nombre del titular no es una transferencia entre cuentas).
TRANSFER_RE = re.compile(r"^\s*(pix|ted|doc|transfer[eê]ncia|transferencia)\b", re.I)

POSITIVE_KINDS = {"refund", "income", "provento", "investment_withdrawal"}
NEGATIVE_KINDS = {"expense", "investment_contribution"}


@dataclass
class Classification:
    kind: str
    category_id: Optional[int] = None
    entity_id: Optional[int] = None
    merchant_normalized: Optional[str] = None
    classification_source: str = "default"
    rule_id: Optional[int] = None
    needs_review: bool = False


class Classifier:
    def __init__(self, db: Session):
        self.rules = (
            db.query(ExpRule).filter(ExpRule.active.is_(True)).order_by(ExpRule.priority, ExpRule.id).all()
        )
        self._compiled = {r.id: re.compile(r.pattern, re.I) for r in self.rules}
        self.unclassified_id = db.query(ExpCategory.id).filter_by(name="Sin clasificar").scalar()
        self.owner_ids = [
            strip_accents(i).lower()
            for a in db.query(ExpAccount).filter(ExpAccount.active.is_(True))
            for i in (a.owner_identifiers or []) if i
        ]

    def classify(self, account_id: int, description_raw: str, counterparty: Optional[str],
                 amount, kind_hint: Optional[str] = None) -> Classification:
        merchant = normalize_merchant(counterparty or description_raw)
        fields = {
            "description_raw": description_raw,
            "counterparty": counterparty or "",
            "merchant_normalized": match_key(merchant),
        }
        positive = amount > 0

        if TRANSFER_RE.search(description_raw) and self._is_own(description_raw, counterparty):
            return self._finish(Classification("own_transfer", merchant_normalized=merchant,
                                               classification_source="own_account"), amount)

        for r in self.rules:
            if r.account_id not in (None, account_id):
                continue
            if (r.amount_sign == "positive" and not positive) or (r.amount_sign == "negative" and positive):
                continue
            if self._compiled[r.id].search(fields.get(r.field, "")):
                kind = _sign_adjust(r.set_kind, amount)
                return self._finish(Classification(
                    kind, r.set_category_id, r.set_entity_id, r.set_merchant or merchant,
                    "rule", r.id, bool(r.set_needs_review)), amount)

        if kind_hint:
            return self._finish(Classification(kind_hint, merchant_normalized=merchant,
                                               classification_source="default"), amount)
        return Classification(
            "expense" if not positive else "income", self.unclassified_id, None, merchant, "default", None, True)

    def _is_own(self, description, counterparty) -> bool:
        hay = strip_accents(f"{description} {counterparty or ''}").lower()
        return any(i in hay for i in self.owner_ids)

    @staticmethod
    def _finish(c: Classification, amount) -> Classification:
        c.needs_review = c.needs_review or sign_inconsistent(c.kind, amount)
        return c


def _sign_adjust(kind: str, amount) -> str:
    """Una regla 'expense' sobre un importe positivo es una devolución (y viceversa)."""
    if kind == "expense" and amount > 0:
        return "refund"
    if kind == "refund" and amount < 0:
        return "expense"
    return kind


def sign_inconsistent(kind: str, amount) -> bool:
    return (kind in POSITIVE_KINDS and amount < 0) or (kind in NEGATIVE_KINDS and amount > 0)
