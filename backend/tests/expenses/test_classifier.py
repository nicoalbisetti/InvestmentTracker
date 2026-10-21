from decimal import Decimal

import pytest

from app.expenses.models import ExpAccount, ExpCategory, ExpRule, ExpTransaction
from app.expenses.services import rules as rules_svc
from app.expenses.services.classifier import Classifier, sign_inconsistent
from app.expenses.services.dedup import assign_hashes
from app.expenses.services.normalize import match_key, normalize_merchant
from app.expenses.parsers.base import ParsedRow
from datetime import date


@pytest.fixture
def clf(db):
    db.add(ExpAccount(name="a", institution="x", country="BR", kind="bank", currency="BRL",
                      owner_identifiers=["Titular Ejemplo"]))
    db.commit()
    return Classifier(db)


D = Decimal


def test_own_transfer_by_identifier_only_for_transfers(clf):
    c = clf.classify(1, 'Pix enviado: "Cp :1-Titular Ejemplo"', "Titular Ejemplo", D("-5"))
    assert (c.kind, c.classification_source) == ("own_transfer", "own_account")
    darf = clf.classify(1, "Pagamento efetuado DARF Titular Ejemplo", None, D("-5"))
    assert darf.kind != "own_transfer"  # sólo descripciones de transferencia


def test_rule_priority_and_sign_adjust(db, clf):
    exp = clf.classify(1, "IOF Exterior R$", None, D("-3"))
    ref = clf.classify(1, "Estorno IOF Exterior R$", None, D("3"))
    assert (exp.kind, ref.kind) == ("expense", "refund")


def test_default_needs_review(clf):
    n = clf.classify(1, "COMERCIO DESCONOCIDO", None, D("-9"))
    m = clf.classify(1, "ALGO ENTRA", None, D("9"))
    assert (n.kind, n.needs_review) == ("expense", True) and (m.kind, m.needs_review) == ("income", True)


def test_sign_rules():
    assert sign_inconsistent("expense", D("5")) and not sign_inconsistent("expense", D("-5"))
    assert sign_inconsistent("investment_withdrawal", D("-1")) and not sign_inconsistent("own_transfer", D("-1"))


def test_kind_hint_when_no_rule(clf):
    assert clf.classify(1, "ALGO DEVUELTO", None, D("4"), "refund").kind == "refund"


def test_pj_income_only_positive(clf):
    assert clf.classify(1, 'Pix recebido: "Cp :9-EMPRESA PJ EJEMPLO"', None, D("10")).kind == "income"
    assert clf.classify(1, 'Pix enviado: "Cp :9-EMPRESA PJ EJEMPLO"', None, D("-10")).needs_review


def test_normalize_merchant():
    assert normalize_merchant("PAO DE ACUCAR-2071") == "PAO DE ACUCAR"
    assert normalize_merchant("RAIA1732") == "RAIA"
    assert normalize_merchant("LOJAS RENNER FL 481") == "LOJAS RENNER"
    assert normalize_merchant("MERPAGO*PANPA") == "PANPA"
    assert match_key("APPLE.COM/BILL") == "APPLECOMBILL"


def _pending(db, desc, amount, source="default", review=True):
    db.add(ExpAccount(name="a", institution="x", country="BR", kind="bank", currency="BRL")) if not db.query(ExpAccount).count() else None
    db.commit()
    from datetime import date as d
    n = db.query(ExpTransaction).count()
    t = ExpTransaction(account_id=1, date=d(2026, 1, 1), description_raw=desc, merchant_normalized=normalize_merchant(desc),
                       amount=amount, currency="BRL", kind="expense", classification_source=source,
                       needs_review=review, dedup_hash=f"h{n}")
    db.add(t); db.commit()
    return t


def test_new_rule_reclassifies_only_pending_non_manual(db):
    a = _pending(db, "PADARIA ZE", -10)
    b = _pending(db, "PADARIA ZE", -12, source="manual", review=False)
    c = _pending(db, "PADARIA ZE", -14, review=False, source="rule")  # ya clasificada
    d = _pending(db, "OTRA COSA", -1)
    cat = db.query(ExpCategory).filter_by(name="Restaurantes y delivery").one()
    rule = ExpRule(pattern="PADARIAZE", field="merchant_normalized", set_kind="expense",
                   set_category_id=cat.id, origin="manual")
    db.add(rule); db.commit()
    assert len(rules_svc.pending_matches(db, rule)) == 1
    assert rules_svc.apply_rule_to_pending(db, rule) == 1
    db.expire_all()
    assert a.category_id == cat.id and a.classification_source == "rule" and not a.needs_review
    assert b.category_id != cat.id and b.classification_source == "manual"
    assert c.category_id != cat.id and d.category_id != cat.id


def test_rules_api_preview_and_create(client, db):
    _pending(db, "PADARIA ZE", -10)
    body = {"pattern": "PADARIAZE", "set_kind": "expense"}
    assert client.post("/api/expenses/rules/preview", json=body).json()["count"] == 1
    assert client.post("/api/expenses/rules/preview", json={**body, "pattern": "("}).status_code == 422
    r = client.post("/api/expenses/rules", json={**body, "apply_to_pending": True})
    assert r.status_code == 201 and r.json()["applied"] == 1


def test_seed_rules_idempotent(db):
    n_before = db.query(ExpRule).count()
    assert n_before > 20
    assert rules_svc.load_seed_rules(db) == 0
    assert db.query(ExpRule).count() == n_before


# --- dedup ---
def row(**kw):
    base = dict(date=date(2026, 3, 24), description_raw="EASYJET", amount=D("-10.00"), currency="BRL")
    base.update(kw)
    return ParsedRow(**base)


def test_dedup_identical_rows_get_distinct_hashes_and_are_stable():
    rows = [row(), row(), row()]
    h = assign_hashes(1, "2026-04", rows)
    assert len(set(h)) == 3 and h == assign_hashes(1, "2026-04", rows)
    assert assign_hashes(2, "2026-04", rows) != h  # cuenta distinta


def test_dedup_prefix_of_same_day_matches():
    full = assign_hashes(1, None, [row(), row(), row()])
    part = assign_hashes(1, None, [row(), row()])
    assert part == full[:2]


def test_dedup_external_id_is_natural_key_without_ordinal():
    a = assign_hashes(1, None, [row(external_id="X1"), row(external_id="X2")])
    b = assign_hashes(1, None, [row(external_id="X2")])
    assert b[0] == a[1]


def test_dedup_amount_representation_is_irrelevant():
    assert assign_hashes(1, None, [row(amount=D("-10"))]) == assign_hashes(1, None, [row(amount=D("-10.00"))])
