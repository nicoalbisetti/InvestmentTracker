import re

from app.expenses.models import ExpAccount, ExpTransaction
from app.expenses.seed.demo import seed_demo
from app.expenses.services import linking, review, summary as S


def test_demo_seed_covers_the_scenarios(db):
    r = seed_demo(db)
    assert r["accounts"] == 4 and r["transactions"] > 100
    s = S.summary(db, "2026-04", "2026-09")
    assert len(s["months"]) == 6 and all(m["expenses"] > 0 and m["income"] > 0 for m in s["months"])
    assert s["months"][2]["proventos"] == 120.0                       # un provento
    # transferencias propias pareadas y excluidas del gasto
    own = db.query(ExpTransaction).filter_by(kind="own_transfer").all()
    assert own and all(t.transfer_group_id for t in own)
    # pagos de tarjeta con fatura quedan cubiertos; el de septiembre cuenta como 'Tarjeta sin detalle'
    pay = linking.payer_card_payments(db)
    assert sum(1 for t in pay if t.statement_batch_id) == 5 and sum(1 for t in pay if not t.statement_batch_id) == 1
    assert s["months"][-1]["no_detail"] == 812.35
    # cuotas y un aporte a inversiones
    assert db.query(ExpTransaction).filter(ExpTransaction.installment_total == 6).count() == 5
    assert db.query(ExpTransaction).filter_by(kind="investment_contribution").count() == 6
    assert review.review_queue(db)["unclassified"] == []              # la demo no deja pendientes


def test_demo_seed_is_deterministic_and_regenerable(db):
    seed_demo(db)
    a = [(t.date, t.description_raw, t.amount) for t in db.query(ExpTransaction).order_by(ExpTransaction.id)]
    seed_demo(db)
    b = [(t.date, t.description_raw, t.amount) for t in db.query(ExpTransaction).order_by(ExpTransaction.id)]
    assert a == b and db.query(ExpAccount).count() == 4


def test_demo_has_no_real_looking_identifiers(db):
    seed_demo(db)
    text = " ".join(t.description_raw for t in db.query(ExpTransaction)) + " ".join(
        i for a in db.query(ExpAccount) for i in a.owner_identifiers)
    assert not re.search(r"\d{8,}", text)
    assert {i for a in db.query(ExpAccount) for i in a.owner_identifiers} == {"titular demo"}


def test_regenerate_endpoint_targets_demo_db(client, monkeypatch, engine):
    from sqlalchemy.orm import sessionmaker
    import app.expenses.routers.demo as demo_router
    monkeypatch.setattr(demo_router, "ExpDemoSessionLocal", sessionmaker(bind=engine))
    r = client.post("/api/expenses/demo/regenerate", headers={"X-Env": "production"})
    assert r.status_code == 200 and r.json()["accounts"] == 4


def test_demo_rules_never_come_from_local_file(db):
    """Si había reglas semilla con nombres reales (p. ej. de un rules.local.json), la demo las reemplaza por el ejemplo."""
    from app.expenses.models import ExpRule
    db.add(ExpRule(pattern="NOMBRE REAL DE UN TERCERO", field="description_raw", set_kind="expense", origin="manual"))   # p. ej. una semilla real que se movió y pasó a manual
    db.commit()
    seed_demo(db)
    patterns = [r.pattern for r in db.query(ExpRule)]
    assert "NOMBRE REAL DE UN TERCERO" not in patterns and any("EJEMPLO" in p for p in patterns)
