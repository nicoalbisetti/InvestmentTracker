from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.expenses.migrations import run_migrations
from app.expenses.models import ExpAccount, ExpImportBatch, ExpRule, ExpTransaction
from app.expenses.services import linking, merchants, review, rules as rules_svc
from app.expenses.services.classifier import Classifier
from app.models.instrument import Instrument
from app.models.transaction import Transaction

D = date
_n = [0]


def acct(db, name, **kw):
    a = ExpAccount(name=name, institution=kw.pop("institution", name), country="BR", kind=kw.pop("kind", "bank"),
                   currency="BRL", **kw)
    db.add(a); db.commit()
    return a


def tx(db, a, d, amount, kind="own_transfer", desc="Transferência", **kw):
    from app.expenses.services.normalize import normalize_merchant
    _n[0] += 1
    t = ExpTransaction(account_id=a.id, date=d, description_raw=desc, merchant_normalized=normalize_merchant(desc), amount=amount,
                       amount_brl=amount, amount_usd=amount / 5, currency="BRL", kind=kind, dedup_hash=f"t2{_n[0]}", **kw)
    db.add(t); db.commit()
    return t


def coverage(db, a, lo, hi):
    db.add(ExpImportBatch(account_id=a.id, file_hash=f"c{a.id}{lo}", parser_key="p", status="confirmed", period_start=lo, period_end=hi))
    db.commit()


# ---------- migración ----------
def test_migration_adds_all_new_columns():
    eng = create_engine("sqlite://", poolclass=StaticPool)
    with eng.begin() as c:
        for t in ("exp_rules", "exp_transactions", "exp_accounts"):
            c.execute(text(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY)"))
    run_migrations(eng); run_migrations(eng)
    ins = inspect(eng)
    assert {"set_needs_review", "set_counterparty_account_id", "set_exclude_from_audit"} <= {c["name"] for c in ins.get_columns("exp_rules")}
    assert {"counterparty_account_id", "exclude_from_audit"} <= {c["name"] for c in ins.get_columns("exp_transactions")}
    assert "itemizes_investments" in {c["name"] for c in ins.get_columns("exp_accounts")}


# ---------- cuenta de contraparte ----------
def test_pairing_only_with_the_declared_counterparty_account(db):
    a, b, c = acct(db, "A"), acct(db, "B"), acct(db, "C")
    out = tx(db, a, D(2026, 1, 10), -100, counterparty_account_id=c.id)
    wrong = tx(db, b, D(2026, 1, 10), 100)           # mismo importe y fecha pero no es la cuenta declarada
    assert linking.link_pairs(db) == 0 and out.transfer_group_id is None
    right = tx(db, c, D(2026, 1, 11), 100)
    assert linking.link_pairs(db) == 1 and out.transfer_group_id == right.transfer_group_id and wrong.transfer_group_id is None


def test_queue_uses_declared_counterparty(db):
    a = acct(db, "A"); inv_acc = acct(db, "XP inversión", has_statements=False); other = acct(db, "Otra")
    coverage(db, a, D(2026, 1, 1), D(2026, 1, 31)); coverage(db, other, D(2026, 1, 1), D(2026, 1, 31))
    tx(db, a, D(2026, 1, 5), -50, counterparty_account_id=inv_acc.id, desc="a la inversión")   # sin extractos: informativo
    tx(db, a, D(2026, 1, 6), -60, counterparty_account_id=other.id, desc="a otra importada")   # su extracto cubre: sospechoso
    tx(db, a, D(2026, 1, 7), -70, desc="sin dato")                                              # otra cuenta cubre la fecha: sospechoso
    q = review.review_queue(db)
    assert [i["description"] for i in q["unpaired_transfers_counterparty_not_imported"]] == ["a la inversión"]
    assert sorted(i["description"] for i in q["unpaired_transfers"]) == ["a otra importada", "sin dato"]


def test_rule_sets_counterparty_and_applies_to_new_rows(db):
    a = acct(db, "A"); inv_acc = acct(db, "XP inversión", has_statements=False)
    db.add(ExpRule(pattern="CONTAINVESTIMENTO", field="merchant_normalized", set_kind="own_transfer",
                   set_counterparty_account_id=inv_acc.id, origin="manual")); db.commit()
    c = Classifier(db).classify(a.id, "Transferência enviada para a conta investimento", None, Decimal("-9"))
    assert c.kind == "own_transfer" and c.counterparty_account_id == inv_acc.id


def test_unpaired_groups_and_apply_counterparty(db):
    a = acct(db, "A"); inv_acc = acct(db, "XP inversión", has_statements=False)
    r1 = tx(db, a, D(2026, 1, 5), -50, desc="Transferência enviada para a conta investimento")
    r2 = tx(db, a, D(2026, 1, 9), -80, desc="Transferência enviada para a conta investimento")
    back = tx(db, a, D(2026, 1, 11), 20, desc="Transferência recebida da conta investimento")
    tx(db, a, D(2026, 1, 12), -5, desc="Dinero reservado Gastos")                      # interno: no aparece
    g = merchants.unpaired_groups(db)
    assert [(x["count"], x["sign"]) for x in g] == [(2, "negative"), (1, "positive")]
    res = merchants.apply_counterparty(db, [{"key": g[0]["key"], "sign": "negative", "account_id": inv_acc.id}])
    assert res[0]["assigned"] == 2
    db.expire_all()
    assert r1.counterparty_account_id == r2.counterparty_account_id == inv_acc.id and back.counterparty_account_id is None
    assert [x["count"] for x in merchants.unpaired_groups(db)] == [1]
    assert merchants.apply_counterparty(db, [{"key": g[0]["key"], "sign": "negative", "account_id": inv_acc.id}])[0]["rule_id"] == res[0]["rule_id"]
    with pytest.raises(ValueError):
        merchants.apply_counterparty(db, [{"key": "X", "account_id": 999}])


# ---------- exclusión de la auditoría ----------
def test_excluded_movements_leave_queue_and_audit(db, inv):
    a = acct(db, "Banco", institution="XP", itemizes_investments=True)
    tx(db, a, D(2026, 3, 5), -100, "investment_contribution", desc="Pix cripto", exclude_from_audit=True)
    tx(db, a, D(2026, 3, 6), -200, "investment_contribution", desc="Pix otro")
    assert [i["description"] for i in review.review_queue(db)["investments_unlinked"]] == ["Pix otro"]
    assert [x["description"] for x in linking.audit_investments(db, inv)["bank_movements_without_transaction"]] == ["Pix otro"]


def test_audit_only_crosses_custodians_that_itemize(db, inv):
    xp = acct(db, "XP cuenta", institution="XP", itemizes_investments=False)
    acct(db, "Inter cuenta", institution="Inter", itemizes_investments=True)
    i1 = Instrument(name="Fondo XP", custodian="XP"); i2 = Instrument(name="CDB Inter", custodian="INTER")
    inv.add_all([i1, i2]); inv.commit()
    inv.add_all([Transaction(instrument_id=i1.id, date=D(2026, 3, 5), type="aplicacion", amount_brl=100.0),
                 Transaction(instrument_id=i2.id, date=D(2026, 3, 5), type="aplicacion", amount_brl=200.0)]); inv.commit()
    got = linking.audit_investments(db, inv)["transactions_without_bank_movement"]
    assert [x["instrument"] for x in got] == ["CDB Inter"]
    xp.itemizes_investments = True; db.commit()
    assert {x["instrument"] for x in linking.audit_investments(db, inv)["transactions_without_bank_movement"]} == {"CDB Inter", "Fondo XP"}


def test_reapply_including_rule_rows_flags_existing_rows(db):
    a = acct(db, "A")
    t = tx(db, a, D(2026, 3, 5), -300, "investment_contribution", desc="Pix enviado para Brasil Bitcoin", classification_source="rule")
    manual = tx(db, a, D(2026, 3, 6), -300, "investment_contribution", desc="Pix enviado para Brasil Bitcoin", classification_source="manual")
    db.add(ExpRule(pattern="Bitcoin", field="description_raw", set_kind="investment_contribution", set_exclude_from_audit=True,
                   origin="manual", priority=1)); db.commit()
    assert rules_svc.reclassify_pending(db)["reclassified"] == 0                          # no re-evalúa filas ya clasificadas
    assert rules_svc.reclassify_pending(db, include_rule_rows=True)["reclassified"] == 1
    db.expire_all()
    assert t.exclude_from_audit and not manual.exclude_from_audit


def test_seed_crypto_rule_is_excluded_from_audit(db):
    a = acct(db, "A")
    c = Classifier(db).classify(a.id, "Pix enviado para Brasil Bitcoin Servicos Digitais", None, Decimal("-1000"))
    assert c.kind == "investment_contribution" and c.exclude_from_audit and not c.needs_review
    d = Classifier(db).classify(a.id, "Debito Online Td: Prot IPCA+ 2032", None, Decimal("-1000"))
    assert d.kind == "investment_contribution" and not d.exclude_from_audit


# ---------- API ----------
def test_api_counterparty_and_audit_flags(client, db):
    a = acct(db, "A"); b = acct(db, "B", has_statements=False)
    t = tx(db, a, D(2026, 1, 5), -50, desc="Transferência enviada X")
    r = client.patch(f"/api/expenses/transactions/{t.id}", json={"counterparty_account_id": b.id, "exclude_from_audit": True}).json()
    assert r["counterparty_account_id"] == b.id and r["exclude_from_audit"] is True
    assert client.patch(f"/api/expenses/transactions/{t.id}", json={"counterparty_account_id": 999}).status_code == 422
    assert client.patch(f"/api/expenses/accounts/{a.id}", json={"itemizes_investments": True}).json()["itemizes_investments"] is True
    t2 = tx(db, a, D(2026, 1, 9), -60, desc="Transferência enviada Y")
    groups = client.get("/api/expenses/review/unpaired-groups").json()
    assert len(groups) == 1
    ok = client.post("/api/expenses/review/unpaired-groups/apply", json={"items": [{"key": groups[0]["key"], "sign": "negative", "account_id": b.id}]})
    assert ok.json()[0]["assigned"] == 1
    assert client.post("/api/expenses/review/unpaired-groups/apply", json={"items": [{"key": "K", "account_id": 999}]}).status_code == 422
    assert client.post("/api/expenses/rules/reapply", params={"include_rule_rows": True}).status_code == 200
