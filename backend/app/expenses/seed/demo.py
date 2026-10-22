"""Datos ficticios para el entorno demo (no usa ni se parece a datos reales).

Dos cuentas bancarias + una billetera + una tarjeta, 6 meses de movimientos con transferencias propias,
pagos de tarjeta con fatura (y uno sin), cuotas, un provento y un aporte a inversiones.
Uso: `python -m app.expenses.seed.demo` (regenera la base demo de gastos).
"""
import hashlib
import random
from datetime import date

from sqlalchemy.orm import Session

from app.expenses.models import (
    ExpAccount, ExpCategory, ExpEntity, ExpImportBatch, ExpLink, ExpTransaction,
)

USD_BRL, ARS_USD = 5.0, 1000.0
MONTHS = [(2026, m) for m in range(4, 10)]

RECURRING = [  # (descripción, categoría, mínimo, máximo, día)
    ("SUPERMERCADO EJEMPLO", "Supermercado", 450, 900, 4), ("SUPERMERCADO EJEMPLO", "Supermercado", 300, 700, 18),
    ("RESTAURANTE MODELO", "Restaurantes y delivery", 90, 260, 9), ("DELIVERY DEMO", "Restaurantes y delivery", 40, 120, 21),
    ("COMPANIA DE LUZ DEMO", "Servicios", 140, 220, 12), ("INTERNET DEMO", "Servicios", 119, 119, 15),
    ("STREAMING DEMO", "Suscripciones", 39.9, 39.9, 7), ("TRANSPORTE APP DEMO", "Transporte", 60, 180, 24),
    ("FARMACIA DEMO", "Salud y farmacia", 40, 150, 27),
]


def _hash(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def seed_demo(db: Session) -> dict:
    """Borra los datos de gastos de la base demo y los vuelve a generar (determinístico)."""
    for model in (ExpLink, ExpTransaction, ExpImportBatch, ExpAccount):
        db.query(model).delete()
    db.commit()
    rnd = random.Random(42)
    cat = {c.name: c.id for c in db.query(ExpCategory)}
    ent = {e.code: e.id for e in db.query(ExpEntity)}

    def account(**kw):
        a = ExpAccount(institution="Demo", owner_identifiers=["titular demo"], **kw)
        db.add(a); db.commit(); return a

    br = account(name="Banco Demo BR", country="BR", kind="bank", currency="BRL", default_entity_id=ent.get("personal"))
    wallet = account(name="Billetera Demo BR", country="BR", kind="wallet", currency="BRL")
    ar = account(name="Banco Demo AR", country="AR", kind="bank", currency="ARS", default_entity_id=ent.get("personal"))
    card = account(name="Tarjeta Demo BR", country="BR", kind="credit_card", currency="BRL", paid_from_account_id=br.id)
    n = [0]

    def add(acc, d, amount, kind, desc, category=None, cur="BRL", **kw):
        n[0] += 1
        brl = amount if cur == "BRL" else amount / ARS_USD * USD_BRL
        db.add(ExpTransaction(
            account_id=acc.id, date=d, description_raw=desc, merchant_normalized=desc, amount=round(amount, 2), currency=cur,
            fx_usd_brl=USD_BRL, fx_ars_usd=ARS_USD if cur == "ARS" else None, amount_brl=round(brl, 2),
            amount_usd=round(brl / USD_BRL, 2), kind=kind, category_id=cat.get(category) if category else None,
            classification_source="rule" if category else "default", dedup_hash=_hash("demo", n[0]), **kw))

    for idx, (y, m) in enumerate(MONTHS):
        add(br, date(y, m, 5), 12500.0, "income", "SALARIO DEMO")
        for desc, c, lo, hi, day in RECURRING:
            add(br, date(y, m, day), -round(rnd.uniform(lo, hi), 2), "expense", desc, c)
        add(br, date(y, m, 10), -1000.0, "own_transfer", "Transferência enviada Billetera Demo")      # par entre cuentas propias
        add(wallet, date(y, m, 10), 1000.0, "own_transfer", "Transferência recebida Banco Demo")
        add(wallet, date(y, m, 22), -round(rnd.uniform(80, 200), 2), "expense", "CAFETERIA DEMO", "Restaurantes y delivery")
        add(br, date(y, m, 28), -2000.0, "investment_contribution", "Aplicacao RF Demo")
        # Argentina: gastos en pesos
        add(ar, date(y, m, 3), 450000.0, "income", "Transferencia recibida ALQUILER DEMO", cur="ARS")
        for day, desc, cname, amt in ((8, "SUPERMERCADO AR DEMO", "Supermercado", 85000), (16, "COMBUSTIBLE DEMO", "Transporte", 60000),
                                      (25, "RESTAURANTE AR DEMO", "Restaurantes y delivery", 45000)):
            add(ar, date(y, m, day), -round(amt * rnd.uniform(0.8, 1.2), 2), "expense", desc, cname, cur="ARS")
        # provento en el 3er mes
        if idx == 2:
            add(br, date(y, m, 20), 120.0, "provento", "Credito B3 PROVENTO DEMO")

    # Tarjeta: facturas de abril a agosto (la de septiembre queda sin detalle) con una compra en 6 cuotas
    due_months = MONTHS[:5]
    for idx, (y, m) in enumerate(due_months):
        due = date(y, m, 20)
        rows = [("TIENDA DEMO ELECTRONICA", "Hogar y mantenimiento", -300.0, (idx + 1, 6)),
                ("AEROLINEA DEMO", "Viajes", -round(rnd.uniform(400, 900), 2), None),
                ("MERCADO DEMO", "Supermercado", -round(rnd.uniform(200, 500), 2), None)]
        total = round(-sum(r[2] for r in rows), 2)
        b = ExpImportBatch(
            account_id=card.id, file_label=f"demo:{y}{m:02d}", file_hash=_hash("batch", y, m), parser_key="xp_card_csv",
            status="confirmed", statement_due_date=due, statement_period=f"{y}-{m:02d}",
            statement_totals={"statement_total": total}, validation=[], rows_total=len(rows), rows_new=len(rows))
        db.add(b); db.commit()
        for desc, c, amt, inst in rows:
            add(card, due, amt, "expense", desc, c, batch_id=b.id, statement_period=b.statement_period,
                purchase_date=date(y, m, 8), installment_number=inst[0] if inst else None, installment_total=inst[1] if inst else None)
        add(br, due, -total, "card_payment", "PAGAMENTO FATURA CARTAO DEMO")
        if idx > 0:
            add(card, due, prev_total, "card_payment", "Pagamento de fatura")
        prev_total = total
    # septiembre: pago de tarjeta sin fatura importada -> 'Tarjeta sin detalle'
    add(br, date(2026, 9, 20), -812.35, "card_payment", "PAGAMENTO FATURA CARTAO DEMO")
    db.commit()

    from app.expenses.services import linking
    linking.rebuild(db)
    return {"accounts": db.query(ExpAccount).count(), "transactions": db.query(ExpTransaction).count()}


if __name__ == "__main__":
    from app.expenses.db import ExpDemoSessionLocal, create_expense_tables, exp_demo_engine
    create_expense_tables([exp_demo_engine], with_demo=False)
    with ExpDemoSessionLocal() as s:
        print(seed_demo(s))
