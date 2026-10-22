"""Cuotas comprometidas: lo que ya está acordado pagar, a partir de la última fatura importada de cada tarjeta.

Es un dato, no una proyección: cada compra en cuotas de la última fatura (n/N) genera las cuotas n+1..N, una por mes
siguiente, al mismo importe. Los importes en BRL usan el tipo de cambio de esa fatura (estimado)."""
import calendar
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.expenses.models import ExpAccount, ExpImportBatch, ExpTransaction


def _add_months(d: date, n: int) -> date:
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def upcoming(db: Session, months: int = 6, today: Optional[date] = None) -> dict:
    today = today or date.today()
    cards, by_month = [], {}
    for acc in db.query(ExpAccount).filter(ExpAccount.kind == "credit_card", ExpAccount.has_statements.is_(True)):
        last = (db.query(ExpImportBatch).filter_by(account_id=acc.id, status="confirmed")
                .filter(ExpImportBatch.statement_due_date.isnot(None))
                .order_by(ExpImportBatch.statement_due_date.desc()).first())
        if last is None:
            continue
        cards.append({"account_id": acc.id, "name": acc.name, "last_statement_due": last.statement_due_date.isoformat(),
                      "stale": (today - last.statement_due_date).days > 45})
        rows = db.query(ExpTransaction).filter(
            ExpTransaction.batch_id == last.id, ExpTransaction.installment_total.isnot(None),
            ExpTransaction.installment_number < ExpTransaction.installment_total, ExpTransaction.amount < 0)
        for t in rows:
            for j in range(1, min(t.installment_total - t.installment_number, months) + 1):
                key = _add_months(last.statement_due_date, j).strftime("%Y-%m")
                m = by_month.setdefault(key, {"month": key, "total_brl": 0.0, "by_card": {}, "items": []})
                brl = -(t.amount_brl or 0.0)
                m["total_brl"] += brl
                m["by_card"][acc.name] = round(m["by_card"].get(acc.name, 0.0) + brl, 2)
                m["items"].append({
                    "card": acc.name, "merchant": t.description_raw[:60], "installment": t.installment_number + j,
                    "of": t.installment_total, "amount": -t.amount, "currency": t.currency, "amount_brl": round(brl, 2)})
    out = []
    for key in sorted(by_month):
        m = by_month[key]
        m["total_brl"] = round(m["total_brl"], 2)
        m["items"].sort(key=lambda i: -i["amount_brl"])
        out.append(m)
    return {"cards": cards, "months": out}
