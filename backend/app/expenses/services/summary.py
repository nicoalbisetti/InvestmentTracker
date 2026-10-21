"""Fuente única de verdad para qué cuenta como gasto/ingreso (resumen, listados, cola de revisión).

Cada movimiento cae en exactamente un balde (ver `bucket`):
  expense   : expense, refund (netea) y pagos de tarjeta SIN fatura cubierta ('Tarjeta sin detalle')
  income    : income
  provento  : provento
  excluded  : own_transfer, card_payment cubierto/interno, investment_*, fx_conversion, unknown
"""
import calendar
from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.expenses.models import ExpAccount, ExpCategory, ExpEntity, ExpImportBatch, ExpTransaction

NO_DETAIL = "Tarjeta sin detalle"
NO_ENTITY = "sin_entidad"


def bucket(tx: ExpTransaction, account_kind: str) -> str:
    k = tx.kind
    if k in ("expense", "refund"):
        return "expense"
    if k == "income":
        return "income"
    if k == "provento":
        return "provento"
    if k == "card_payment" and account_kind != "credit_card" and tx.statement_batch_id is None and tx.amount < 0:
        return "expense"  # tarjeta sin detalle
    return "excluded"


def is_no_detail(tx: ExpTransaction, account_kind: str) -> bool:
    return tx.kind == "card_payment" and bucket(tx, account_kind) == "expense"


def _ym(d: date) -> str:
    return d.strftime("%Y-%m")


def _value(tx: ExpTransaction, currency: str) -> Optional[float]:
    if currency == "BRL":
        return tx.amount_brl
    if currency == "USD":
        return tx.amount_usd
    return tx.amount  # native


def query_transactions(db: Session, date_from: Optional[date] = None, date_to: Optional[date] = None,
                       entity: Optional[str] = None, country: Optional[str] = None):
    accounts = {a.id: a for a in db.query(ExpAccount)}
    ents = {e.id: e.code for e in db.query(ExpEntity)}
    q = db.query(ExpTransaction)
    if date_from:
        q = q.filter(ExpTransaction.date >= date_from)
    if date_to:
        q = q.filter(ExpTransaction.date <= date_to)
    out = []
    for t in q:
        acc = accounts[t.account_id]
        if country and acc.country != country:
            continue
        code = ents.get(t.entity_id or acc.default_entity_id, NO_ENTITY)
        if entity and code != entity:
            continue
        out.append((t, acc, code))
    return out


def _month_start(ym: str) -> date:
    y, m = ym.split("-")
    return date(int(y), int(m), 1)


def _last_day(ym: str) -> date:
    y, m = int(ym[:4]), int(ym[5:])
    return date(y, m, calendar.monthrange(y, m)[1])


def summary(db: Session, month_from: Optional[str] = None, month_to: Optional[str] = None,
            entity: Optional[str] = None, country: Optional[str] = None, currency: str = "BRL") -> dict:
    d_from = _month_start(month_from) if month_from else None
    d_to = _last_day(month_to) if month_to else None
    cats = {c.id: c.name for c in db.query(ExpCategory)}
    unclassified = next((i for i, n in cats.items() if n == "Sin clasificar"), None)
    no_detail = next((i for i, n in cats.items() if n == NO_DETAIL), None)

    rows = query_transactions(db, d_from, d_to, entity, country)
    currencies = ["BRL"] if currency == "BRL" else ["USD"] if currency == "USD" else sorted({t.currency for t, _, _ in rows})

    def build(cur: Optional[str]) -> dict:
        months: dict[str, dict] = defaultdict(lambda: {
            "expenses": 0.0, "income": 0.0, "proventos": 0.0, "by_category": defaultdict(float),
            "by_entity": defaultdict(float), "no_detail": 0.0})
        missing_fx = 0
        for t, acc, code in rows:
            if cur and currency == "native" and t.currency != cur:
                continue
            b = bucket(t, acc.kind)
            if b == "excluded":
                continue
            v = _value(t, currency)
            if v is None:
                missing_fx += 1
                continue
            m = months[_ym(t.date)]
            if b == "expense":
                m["expenses"] += -v
                cat = NO_DETAIL if is_no_detail(t, acc.kind) else cats.get(t.category_id or unclassified, "Sin clasificar")
                m["by_category"][cat] += -v
                m["by_entity"][code] += -v
                if is_no_detail(t, acc.kind):
                    m["no_detail"] += -v
            elif b == "income":
                m["income"] += v
            else:
                m["proventos"] += v
        out = []
        for ym in sorted(months):
            m = months[ym]
            out.append({
                "month": ym, "expenses": round(m["expenses"], 2), "income": round(m["income"], 2),
                "proventos": round(m["proventos"], 2), "savings": round(m["income"] - m["expenses"], 2),
                "no_detail": round(m["no_detail"], 2),
                "by_category": {k: round(v, 2) for k, v in sorted(m["by_category"].items())},
                "by_entity": {k: round(v, 2) for k, v in sorted(m["by_entity"].items())},
            })
        return {"months": out, "rows_without_fx": missing_fx}

    total = len(rows)
    pending = sum(1 for t, _, _ in rows if t.needs_review)
    result = {
        "currency": currency,
        "pending_review_pct": round(100 * pending / total, 1) if total else 0.0,
        "coverage": coverage(db),
    }
    if currency == "native":
        result["by_currency"] = {c: build(c) for c in currencies}
    else:
        result.update(build(None))
    return result


def coverage(db: Session) -> list[dict]:
    """Meses con extracto importado por cuenta, para no confundir 'sin datos' con 'cero gasto'."""
    out = []
    for a in db.query(ExpAccount).order_by(ExpAccount.id):
        months: set[str] = set()
        for b in db.query(ExpImportBatch).filter_by(account_id=a.id, status="confirmed"):
            if b.statement_period:
                months.add(b.statement_period)
            elif b.period_start and b.period_end:
                y, m = b.period_start.year, b.period_start.month
                while (y, m) <= (b.period_end.year, b.period_end.month):
                    months.add(f"{y:04d}-{m:02d}"); y, m = (y + (m == 12), 1 if m == 12 else m + 1)
        out.append({"account_id": a.id, "name": a.name, "months": sorted(months)})
    return out
