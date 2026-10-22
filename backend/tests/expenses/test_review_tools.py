from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.expenses.migrations import run_migrations
from app.expenses.models import ExpAccount, ExpCategory, ExpRule, ExpTransaction
from app.expenses.services import merchants, rules as rules_svc
from app.expenses.services.classifier import Classifier

_n = [0]


def acct(db):
    a = ExpAccount(name="A", institution="X", country="BR", kind="bank", currency="BRL")
    db.add(a); db.commit()
    return a


def pending(db, a, desc, amount=-10.0, source="default", merchant=None, review=True, d=date(2026, 1, 5)):
    from app.expenses.services.normalize import normalize_merchant
    _n[0] += 1
    t = ExpTransaction(account_id=a.id, date=d, description_raw=desc, merchant_normalized=merchant or normalize_merchant(desc),
                       amount=amount, amount_brl=amount, currency="BRL", kind="expense" if amount < 0 else "income",
                       classification_source=source, needs_review=review, dedup_hash=f"r{_n[0]}")
    db.add(t); db.commit()
    return t


def cat(db, name):
    return db.query(ExpCategory).filter_by(name=name).one().id


# ---------- reglas que dejan la fila en revisión ----------
def test_rule_can_classify_but_keep_row_in_review(db):
    a = acct(db)
    db.add(ExpRule(pattern="VIVO", field="description_raw", set_kind="expense", set_category_id=cat(db, "Servicios"),
                   set_needs_review=True, origin="manual")); db.commit()
    c = Classifier(db).classify(a.id, "Pagamento de Convenio VIVO SP", None, Decimal("-80"))
    assert (c.kind, c.category_id, c.classification_source, c.needs_review) == ("expense", cat(db, "Servicios"), "rule", True)


def test_seed_rule_for_telephony_requires_review(db):
    a = acct(db)
    c = Classifier(db).classify(a.id, 'Pagamento de Convenio: "VIVO SP"', None, Decimal("-80"))
    assert c.category_id == cat(db, "Servicios") and c.needs_review and c.entity_id is None


def test_migration_adds_column_to_old_schema():
    eng = create_engine("sqlite://", poolclass=StaticPool)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE exp_rules (id INTEGER PRIMARY KEY, pattern VARCHAR)"))
    run_migrations(eng); run_migrations(eng)  # idempotente
    assert "set_needs_review" in {c["name"] for c in inspect(eng).get_columns("exp_rules")}


# ---------- reaplicar reglas ----------
def test_reclassify_pending_only_touches_rows_that_now_match(db):
    a = acct(db)
    hit = pending(db, a, "PADARIA ZE")
    miss = pending(db, a, "OTRA COSA")
    man = pending(db, a, "PADARIA ZE", source="manual", review=False)
    db.add(ExpRule(pattern="PADARIAZE", field="merchant_normalized", set_kind="expense",
                   set_category_id=cat(db, "Restaurantes y delivery"), origin="manual")); db.commit()
    assert rules_svc.reclassify_pending(db) == {"reclassified": 1, "resolved": 1}
    db.expire_all()
    assert hit.category_id == cat(db, "Restaurantes y delivery") and not hit.needs_review and hit.classification_source == "rule"
    assert miss.needs_review and miss.classification_source == "default"
    assert man.category_id != cat(db, "Restaurantes y delivery")


# ---------- grupos por comercio ----------
def test_groups_are_sorted_by_amount_and_split_by_sign(db):
    a = acct(db)
    pending(db, a, "PADARIA ZE", -10); pending(db, a, "PADARIA ZE", -15)
    pending(db, a, "GRANDE LOJA", -500)
    pending(db, a, "PADARIA ZE", 7)                       # mismo comercio, otro signo: grupo aparte
    pending(db, a, "YA CLASIFICADO", -9, source="rule", review=False)
    pending(db, a, "MANUAL", -9, source="manual", review=True)
    g = merchants.pending_groups(db)
    assert [(x["key"], x["sign"], x["count"]) for x in g] == [
        ("GRANDELOJA", "negative", 1), ("PADARIAZE", "negative", 2), ("PADARIAZE", "positive", 1)]
    assert g[1]["total_brl"] == 25.0 and g[1]["sample"] == ["PADARIA ZE", "PADARIA ZE"]


def test_apply_group_creates_anchored_rule_and_is_idempotent(db):
    a = acct(db)
    p1 = pending(db, a, "PADARIA ZE", -10); p2 = pending(db, a, "PADARIA ZE", -20)
    other = pending(db, a, "PADARIA ZE DOIS", -5)         # un comercio distinto no debe matchear (regla anclada)
    man = pending(db, a, "PADARIA ZE", -30, source="manual")
    item = {"key": "PADARIAZE", "sign": "negative", "kind": "expense", "category_id": cat(db, "Restaurantes y delivery")}
    r = merchants.apply_groups(db, [item])
    assert r[0]["applied"] == 2
    db.expire_all()
    assert p1.category_id == p2.category_id == cat(db, "Restaurantes y delivery") and not p1.needs_review
    assert other.needs_review and man.classification_source == "manual"
    assert merchants.apply_groups(db, [item])[0]["rule_id"] == r[0]["rule_id"]
    assert db.query(ExpRule).filter_by(pattern="^PADARIAZE$").count() == 1


def test_apply_group_validation(db):
    import pytest
    with pytest.raises(ValueError):
        merchants.apply_groups(db, [{"key": "X", "kind": "nope"}])
    with pytest.raises(ValueError):
        merchants.apply_groups(db, [{"key": "---", "kind": "expense"}])


def test_review_endpoints(client, db):
    a = acct(db)
    pending(db, a, "PADARIA ZE", -10)
    groups = client.get("/api/expenses/review/merchant-groups").json()
    assert groups[0]["key"] == "PADARIAZE"
    body = {"items": [{"key": "PADARIAZE", "sign": "negative", "kind": "expense", "category_id": cat(db, "Otros")}]}
    assert client.post("/api/expenses/review/merchant-groups/apply", json=body).json()[0]["applied"] == 1
    assert client.get("/api/expenses/review/merchant-groups").json() == []
    assert client.post("/api/expenses/review/merchant-groups/apply", json={"items": [{"key": "X", "kind": "bad"}]}).status_code == 422
    assert client.post("/api/expenses/rules/reapply").json() == {"reclassified": 0, "resolved": 0}
    r = client.post("/api/expenses/rules", json={"pattern": "XYZ", "set_kind": "expense", "set_needs_review": True}).json()
    assert r["set_needs_review"] is True
