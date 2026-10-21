from sqlalchemy.orm import Session

from app.expenses.models import ExpAccount, ExpImportBatch, ExpTransaction
from app.expenses.services import linking
from app.expenses.services.classifier import sign_inconsistent
from app.expenses.services.summary import bucket


# Descripciones que delatan una cuenta propia que no se importa (p. ej. la cuenta de inversión del banco).
NOT_IMPORTED_MARKERS = ("conta investimento",)
# Movimientos entre bolsillos de una misma cuenta (p. ej. reservas de Mercado Pago): no tienen par por diseño.
INTERNAL_MARKERS = ("dinero reservado", "dinero retirado")


def _item(t: ExpTransaction, **extra) -> dict:
    return {"id": t.id, "date": t.date.isoformat(), "description": t.description_raw, "amount": t.amount,
            "currency": t.currency, "kind": t.kind, **extra}


def review_queue(db: Session) -> dict:
    accounts = {a.id: a for a in db.query(ExpAccount)}
    txs = db.query(ExpTransaction).order_by(ExpTransaction.date).all()
    unclassified, sign, fx_missing, fx_estimated = [], [], [], []
    for t in txs:
        if sign_inconsistent(t.kind, t.amount):
            sign.append(_item(t))
        elif t.needs_review:
            unclassified.append(_item(t))
        if t.amount_brl is None or t.amount_usd is None:
            fx_missing.append(_item(t))
        elif t.fx_estimated:
            fx_estimated.append(_item(t))

    # cobertura: ¿hay extracto de otra cuenta propia que cubra la fecha? si no, la contraparte no se importó
    spans = [(b.account_id, b.period_start, b.period_end) for b in db.query(ExpImportBatch).filter_by(status="confirmed")
             if b.period_start and b.period_end]
    unpaired, unpaired_info = [], []
    for t in txs:
        if t.kind == "own_transfer" and t.transfer_group_id is None:
            if any(m in t.description_raw.lower() for m in INTERNAL_MARKERS):
                continue
            covered = (not any(m in t.description_raw.lower() for m in NOT_IMPORTED_MARKERS)
                       and any(a != t.account_id and s <= t.date <= e for a, s, e in spans))
            # con otra cuenta propia importada que cubre la fecha, la falta de par es sospechosa;
            # si no, es 'contraparte no importada' (informativo)
            (unpaired if covered else unpaired_info).append(_item(t))

    card_uncovered, card_inexact = [], []
    for t in linking.payer_card_payments(db):
        if t.statement_batch_id is None:
            card_uncovered.append(_item(t))
        elif not linking.is_exact_statement_link(db, t):
            card_inexact.append(_item(t, statement_batch_id=t.statement_batch_id))
    by_id = {t.id: t for t in txs}
    suggestions = [{**s, "out": _item(by_id[s["out_id"]]), "in": _item(by_id[s["in_id"]])}
                   for s in linking.pair_suggestions(db)]
    return {
        "unclassified": unclassified, "sign_inconsistent": sign,
        "unpaired_transfers": unpaired, "unpaired_transfers_counterparty_not_imported": unpaired_info, "pair_suggestions": suggestions,
        "card_payments_without_statement": card_uncovered, "card_payments_inexact": card_inexact,
        "fx_missing": fx_missing, "fx_estimated": fx_estimated,
        "investments_unlinked": _unlinked(db, ("investment_contribution", "investment_withdrawal"), "investment", by_id),
        "proventos_unlinked": _unlinked(db, ("provento",), "provento", by_id),
    }


def _unlinked(db: Session, kinds, link_type: str, by_id: dict) -> list[dict]:
    """Movimientos de inversión/provento sin ningún vínculo sugerido ni confirmado."""
    from app.expenses.models import ExpLink
    linked = {i for (i,) in db.query(ExpLink.exp_transaction_id).filter(
        ExpLink.link_type == link_type, ExpLink.status.in_(("suggested", "confirmed")))}
    return [_item(t) for t in by_id.values() if t.kind in kinds and t.id not in linked]
