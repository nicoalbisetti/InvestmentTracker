from datetime import date

import pytest

from app.expenses.models import ExpAccount, ExpCategory, ExpImportBatch, ExpTransaction
from app.expenses.services import linking, review, summary as S

_n = [0]


def acct(db, name, kind="bank", paid_from=None, country="BR", cur="BRL"):
    a = ExpAccount(name=name, institution="x", country=country, kind=kind, currency=cur, paid_from_account_id=paid_from)
    db.add(a); db.commit()
    return a


def tx(db, account, d, amount, kind="expense", cur="BRL", cat=None, brl=None, usd=None, **kw):
    _n[0] += 1
    t = ExpTransaction(account_id=account.id, date=d, description_raw=kw.pop("desc", f"t{_n[0]}"), amount=amount,
                       currency=cur, kind=kind, category_id=cat, amount_brl=amount if brl is None and cur == "BRL" else brl,
                       amount_usd=amount / 5 if usd is None else usd, dedup_hash=f"h{_n[0]}", **kw)
    db.add(t); db.commit()
    return t


def batch(db, account, due, total, status="confirmed"):
    b = ExpImportBatch(account_id=account.id, file_hash=f"f{_n[0]}{due}", parser_key="xp_card_csv", status=status,
                       statement_due_date=due, statement_period=due.strftime("%Y-%m"),
                       statement_totals={"statement_total": total})
    _n[0] += 1
    db.add(b); db.commit()
    return b


D = date


# ---------- pares ----------
def test_unique_pair_within_one_day_is_confirmed(db):
    a, b = acct(db, "A"), acct(db, "B")
    o = tx(db, a, D(2026, 1, 10), -100, "own_transfer")
    i = tx(db, b, D(2026, 1, 11), 100, "own_transfer")
    assert linking.link_pairs(db) == 1
    assert o.transfer_group_id == i.transfer_group_id == min(o.id, i.id)


def test_two_day_gap_is_only_suggested(db):
    a, b = acct(db, "A"), acct(db, "B")
    o = tx(db, a, D(2026, 1, 10), -100, "own_transfer")
    i = tx(db, b, D(2026, 1, 12), 100, "own_transfer")
    assert linking.link_pairs(db) == 0 and o.transfer_group_id is None
    sug = linking.pair_suggestions(db)
    assert [(s["out_id"], s["in_id"]) for s in sug] == [(o.id, i.id)]
    assert linking.rebuild(db)["pairs"] == 0  # idempotente


def test_same_account_and_different_currency_never_pair(db):
    a, b = acct(db, "A"), acct(db, "B")
    tx(db, a, D(2026, 1, 10), -100, "own_transfer"); tx(db, a, D(2026, 1, 10), 100, "own_transfer")
    tx(db, b, D(2026, 1, 10), 100, "own_transfer", cur="USD")
    assert linking.link_pairs(db) == 0


def test_repeated_amounts_resolve_by_nearest_date(db):
    a, b = acct(db, "A"), acct(db, "B")
    o1 = tx(db, a, D(2026, 2, 1), -500, "own_transfer"); o2 = tx(db, a, D(2026, 2, 2), -500, "own_transfer")
    i1 = tx(db, b, D(2026, 2, 1), 500, "own_transfer"); i2 = tx(db, b, D(2026, 2, 3), 500, "own_transfer")
    linking.link_pairs(db)
    assert o1.transfer_group_id == i1.transfer_group_id and o2.transfer_group_id is not None
    assert o1.transfer_group_id != o2.transfer_group_id


def test_ambiguous_equal_candidates_stay_unlinked(db):
    a, b = acct(db, "A"), acct(db, "B")
    tx(db, a, D(2026, 3, 5), -70, "own_transfer")
    tx(db, b, D(2026, 3, 5), 70, "own_transfer"); tx(db, b, D(2026, 3, 5), 70, "own_transfer")
    assert linking.link_pairs(db) == 0 and len(linking.pair_suggestions(db)) == 2


def test_unpaired_info_vs_suspicious(db):
    a, b = acct(db, "A"), acct(db, "B")
    tx(db, a, D(2026, 1, 10), -9, "own_transfer", desc="Transferência enviada para a conta investimento")
    tx(db, a, D(2026, 1, 11), -8, "own_transfer", desc="Pix enviado a otro banco")
    for acc in (a, b):
        db.add(ExpImportBatch(account_id=acc.id, file_hash=f"s{acc.id}", parser_key="p", status="confirmed",
                              period_start=D(2026, 1, 1), period_end=D(2026, 1, 31)))
    db.commit()
    q = review.review_queue(db)
    assert len(q["unpaired_transfers_counterparty_not_imported"]) == 1 and len(q["unpaired_transfers"]) == 1


# ---------- tarjetas ----------
@pytest.fixture
def cards(db):
    pay = acct(db, "Banco")
    card = acct(db, "Tarjeta", kind="credit_card", paid_from=pay.id)
    return pay, card


def test_payment_exact_total_links_to_statement(db, cards):
    pay, card = cards
    b = batch(db, card, D(2026, 3, 20), 14961.54)
    p = tx(db, pay, D(2026, 3, 20), -14961.54, "card_payment")
    linking.link_statements(db)
    assert p.statement_batch_id == b.id and linking.is_exact_statement_link(db, p)


def test_partial_payments_are_covered_without_double_counting(db, cards):
    pay, card = cards
    b = batch(db, card, D(2026, 3, 20), 1000.00)
    p1 = tx(db, pay, D(2026, 3, 18), -600, "card_payment"); p2 = tx(db, pay, D(2026, 3, 25), -400, "card_payment")
    linking.link_statements(db)
    assert p1.statement_batch_id == p2.statement_batch_id == b.id
    assert S.bucket(p1, "bank") == "excluded"
    assert len(review.review_queue(db)["card_payments_inexact"]) == 2


def test_payment_without_statement_counts_as_no_detail_until_batch_imported(db, cards):
    pay, card = cards
    p = tx(db, pay, D(2026, 4, 20), -125.58, "card_payment")
    linking.link_statements(db)
    assert p.statement_batch_id is None and S.bucket(p, "bank") == "expense"
    batch(db, card, D(2026, 4, 20), 125.58)
    linking.rebuild(db)
    assert S.bucket(p, "bank") == "excluded"  # ya hay detalle: deja de contarse


def test_far_payment_not_linked(db, cards):
    pay, card = cards
    batch(db, card, D(2026, 3, 20), 100)
    p = tx(db, pay, D(2026, 2, 1), -100, "card_payment")  # pagaba el resumen anterior (no importado)
    linking.link_statements(db)
    assert p.statement_batch_id is None


def test_card_internal_payment_pairs_with_payer_payment(db, cards):
    pay, card = cards
    a = tx(db, pay, D(2026, 3, 20), -500, "card_payment")
    b = tx(db, card, D(2026, 4, 20), 500, "card_payment")  # crédito en la fatura siguiente
    linking.link_pairs(db)
    assert a.transfer_group_id == b.transfer_group_id
    assert S.bucket(b, "credit_card") == "excluded"


# ---------- resumen ----------
def test_summary_buckets_and_consistency(db, cards):
    pay, card = cards
    cat = db.query(ExpCategory).filter_by(name="Supermercado").one().id
    tx(db, pay, D(2026, 1, 5), -100, "expense", cat=cat)
    tx(db, pay, D(2026, 1, 6), 30, "refund", cat=cat)
    tx(db, pay, D(2026, 1, 7), 1000, "income")
    tx(db, pay, D(2026, 1, 8), 50, "provento")
    tx(db, pay, D(2026, 1, 9), -999, "own_transfer")
    tx(db, pay, D(2026, 1, 10), -999, "investment_contribution")
    tx(db, pay, D(2026, 1, 11), -999, "fx_conversion")
    tx(db, pay, D(2026, 1, 12), -40, "card_payment")  # sin detalle
    b = batch(db, card, D(2026, 2, 20), 70)
    tx(db, pay, D(2026, 2, 20), -70, "card_payment")
    tx(db, card, D(2026, 2, 20), -70, "expense", cat=cat)
    linking.rebuild(db)
    s = S.summary(db, "2026-01", "2026-02")
    jan, feb = s["months"]
    assert jan["expenses"] == 110.0 and jan["income"] == 1000 and jan["proventos"] == 50 and jan["savings"] == 890
    assert jan["by_category"] == {"Supermercado": 70.0, "Tarjeta sin detalle": 40.0} and jan["no_detail"] == 40
    assert feb["expenses"] == 70.0  # sólo el consumo de la fatura; el pago cubierto no suma


def test_every_transaction_falls_in_exactly_one_bucket(db, cards):
    from app.expenses.models.transaction import KINDS
    pay, card = cards
    for k in KINDS:
        tx(db, pay, D(2026, 1, 1), -1, k)
    kinds_by_bucket = {}
    for t in db.query(ExpTransaction):
        kinds_by_bucket.setdefault(S.bucket(t, "bank"), []).append(t.kind)
    assert sum(len(v) for v in kinds_by_bucket.values()) == len(KINDS)
    assert set(kinds_by_bucket) <= {"expense", "income", "income_pending", "provento", "excluded"}


def test_summary_filters_and_native_currency(db):
    br = acct(db, "BR1"); ar = acct(db, "AR1", country="AR", cur="ARS")
    tx(db, br, D(2026, 1, 5), -100, "expense")
    tx(db, ar, D(2026, 1, 6), -3000, "expense", cur="ARS", brl=-15.0, usd=-3.0)
    assert S.summary(db, country="AR")["months"][0]["expenses"] == 15.0
    assert S.summary(db, currency="USD")["months"][0]["expenses"] == 23.0  # -100/5 -> 20 + 3
    nat = S.summary(db, currency="native")["by_currency"]
    assert nat["BRL"]["months"][0]["expenses"] == 100 and nat["ARS"]["months"][0]["expenses"] == 3000
    assert S.summary(db, month_from="2026-02")["months"] == []


def test_rows_without_fx_are_reported_not_summed(db):
    a = acct(db, "A")
    t = tx(db, a, D(2026, 1, 5), -100, "expense")
    t.amount_brl = None; db.commit()
    s = S.summary(db)
    assert s["rows_without_fx"] == 1 and s["months"] == []


def test_coverage_lists_months(db, cards):
    pay, card = cards
    batch(db, card, D(2026, 3, 20), 1)
    db.add(ExpImportBatch(account_id=pay.id, file_hash="c", parser_key="p", status="confirmed",
                          period_start=D(2026, 1, 15), period_end=D(2026, 3, 2))); db.commit()
    cov = {c["name"]: c["months"] for c in S.coverage(db)}
    assert cov["Tarjeta"] == ["2026-03"] and cov["Banco"] == ["2026-01", "2026-02", "2026-03"]


# ---------- API ----------
def test_patch_manual_create_rule_and_unlink(client, db):
    a, b = acct(db, "A"), acct(db, "B")
    o = tx(db, a, D(2026, 1, 10), -100, "own_transfer"); i = tx(db, b, D(2026, 1, 10), 100, "own_transfer")
    linking.link_pairs(db)
    cat = db.query(ExpCategory).filter_by(name="Ropa y calzado").one().id
    p1 = tx(db, a, D(2026, 1, 1), -10, "expense", desc="ADIDAS", needs_review=True, merchant_normalized="ADIDAS")
    p2 = tx(db, a, D(2026, 1, 2), -20, "expense", desc="ADIDAS", needs_review=True, merchant_normalized="ADIDAS")
    man = tx(db, a, D(2026, 1, 3), -30, "expense", desc="ADIDAS", classification_source="manual", merchant_normalized="ADIDAS")
    r = client.patch(f"/api/expenses/transactions/{p1.id}", json={"category_id": cat, "create_rule": True})
    assert r.status_code == 200 and r.json()["rule_applied_to"] == 1
    db.expire_all()
    assert p2.category_id == cat and p2.classification_source == "rule" and man.category_id != cat
    assert p1.classification_source == "manual" and not p1.needs_review
    # cambiar el kind de una transferencia rompe el par
    client.patch(f"/api/expenses/transactions/{o.id}", json={"kind": "expense"})
    db.expire_all()
    assert i.transfer_group_id is None
    assert client.patch(f"/api/expenses/transactions/{o.id}", json={"kind": "nope"}).status_code == 422


def test_list_filters_and_pagination(client, db):
    a = acct(db, "A")
    for n in range(5):
        tx(db, a, D(2026, 1, 1 + n), -10 * (n + 1), "expense", desc=f"cosa {n}")
    r = client.get("/api/expenses/transactions", params={"page_size": 2, "page": 2, "from": "2026-01-01"}).json()
    assert r["total"] == 5 and len(r["items"]) == 2 and r["items"][0]["description"] == "cosa 2"
    assert client.get("/api/expenses/transactions", params={"q": "cosa 4"}).json()["total"] == 1


def test_bulk_and_summary_endpoint(client, db):
    a = acct(db, "A")
    ids = [tx(db, a, D(2026, 1, 1 + n), -10, "expense", needs_review=True).id for n in range(3)]
    cat = db.query(ExpCategory).filter_by(name="Otros").one().id
    assert client.post("/api/expenses/transactions/bulk", json={"ids": ids, "category_id": cat}).json() == {"updated": 3}
    s = client.get("/api/expenses/summary", params={"from": "2026-01", "to": "2026-01"}).json()
    assert s["months"][0]["by_category"] == {"Otros": 30.0} and s["pending_review_pct"] == 0.0
    assert client.get("/api/expenses/summary", params={"currency": "X"}).status_code == 422


def test_pair_manual_confirm_and_reject(client, db):
    a, b = acct(db, "A"), acct(db, "B")
    o = tx(db, a, D(2026, 1, 10), -100, "own_transfer"); i = tx(db, b, D(2026, 1, 13), 100, "own_transfer")
    gid = client.post("/api/expenses/links/pairs", json={"out_id": o.id, "in_id": i.id}).json()["group_id"]
    db.expire_all(); assert o.transfer_group_id == gid
    assert client.delete(f"/api/expenses/links/pairs/{gid}").json() == {"unlinked": 2}


def test_fx_recompute_only_touches_range(client, db):
    from app.expenses.services import fx
    a = acct(db, "A")
    t1 = tx(db, a, D(2026, 3, 10), -50, "expense", brl=-50, usd=0.0)
    t2 = tx(db, a, D(2026, 4, 10), -50, "expense", brl=-50, usd=0.0)
    fx.set_manual_rate(db, "USDBRL_PTAX", D(2026, 3, 10), 10.0)
    assert client.post("/api/expenses/fx/recompute", params={"from": "2026-03-01", "to": "2026-03-31"}).json() == {"recomputed": 1}
    db.expire_all()
    assert t1.amount_usd == -5.0 and t2.amount_usd == 0.0


# ---------- adopción de contraparte ----------
def test_own_transfer_adopts_unrecognized_exact_counterpart(db):
    a, b = acct(db, "A"), acct(db, "B")
    o = tx(db, a, D(2026, 4, 10), -800000, "own_transfer")
    i = tx(db, b, D(2026, 4, 10), 800000, "income", needs_review=True)
    assert linking.rebuild(db)["adopted"] == 1
    assert i.kind == "own_transfer" and i.classification_source == "own_account" and not i.needs_review
    assert o.transfer_group_id == i.transfer_group_id is not None


def test_adoption_never_touches_manual_or_far_or_ambiguous(db):
    a, b = acct(db, "A"), acct(db, "B")
    tx(db, a, D(2026, 4, 10), -100, "own_transfer")
    man = tx(db, b, D(2026, 4, 10), 100, "income", classification_source="manual")
    far = tx(db, b, D(2026, 4, 14), 100, "income")
    assert linking.adopt_counterparts(db) == 0 and man.kind == far.kind == "income"
    tx(db, a, D(2026, 5, 1), -50, "own_transfer")
    x1 = tx(db, b, D(2026, 5, 1), 50, "income"); x2 = tx(db, b, D(2026, 5, 1), 50, "income")
    assert linking.adopt_counterparts(db) == 0 and x1.kind == x2.kind == "income"


def test_internal_pocket_moves_do_not_clutter_the_queue(db):
    a = acct(db, "MP")
    tx(db, a, D(2026, 1, 10), -100, "own_transfer", desc="Dinero reservado Gastos")
    tx(db, a, D(2026, 1, 11), 100, "own_transfer", desc="Dinero retirado Gastos")
    q = review.review_queue(db)
    assert q["unpaired_transfers"] == [] and q["unpaired_transfers_counterparty_not_imported"] == []


def test_payment_naming_a_brand_is_not_covered_by_another_brands_statement(db):
    pay = acct(db, "Banco")
    visa = acct(db, "Banco VISA", kind="credit_card", paid_from=pay.id)
    acct(db, "Mastercard AR", kind="credit_card", paid_from=pay.id)  # sin resúmenes
    batch(db, visa, D(2026, 3, 9), 1000.00)
    mc = tx(db, pay, D(2026, 3, 9), -26556, "card_payment", desc="Pago de servicios Mastercard: ***0836")
    vz = tx(db, pay, D(2026, 3, 9), -1000, "card_payment", desc="Pago tarjeta de credito visa Deb. automatico")
    generic = tx(db, pay, D(2026, 3, 10), -300, "card_payment", desc="Pago de tarjeta de credito")
    linking.link_statements(db)
    assert mc.statement_batch_id is None and S.bucket(mc, "bank") == "expense"   # Tarjeta sin detalle
    assert vz.statement_batch_id is not None and generic.statement_batch_id is not None


def test_ar_statement_totals_per_currency_and_pair_makes_link_exact(db):
    pay = acct(db, "Banco", country="AR", cur="ARS")
    card = acct(db, "Banco VISA", kind="credit_card", paid_from=pay.id, country="AR", cur="ARS")
    b = batch(db, card, D(2026, 3, 9), 0)
    b.statement_totals = {"ARS": 1672047.98, "USD": 3.07}
    db.commit()
    p = tx(db, pay, D(2026, 3, 9), -1676453.43, "card_payment", cur="ARS", desc="Pago tarjeta de credito visa")
    c = tx(db, card, D(2026, 4, 10), 1676453.43, "card_payment", cur="ARS", desc="SU PAGO EN PESOS")
    c.date = D(2026, 3, 9); db.commit()
    linking.rebuild(db)
    assert p.statement_batch_id == b.id and p.transfer_group_id == c.transfer_group_id is not None
    assert linking.is_exact_statement_link(db, p)  # débito = pesos + USD x TC: se prueba por el par


def test_unclassified_inflows_do_not_inflate_income(db):
    a = acct(db, "A")
    tx(db, a, D(2026, 1, 5), 1000, "income")                                              # clasificado
    pend = tx(db, a, D(2026, 1, 6), 5000, "income", needs_review=True)                    # default + revisión
    s = S.summary(db)["months"][0]
    assert s["income"] == 1000 and s["income_pending"] == 5000 and s["savings"] == 1000
    pend.classification_source, pend.needs_review = "manual", False; db.commit()
    s = S.summary(db)["months"][0]
    assert s["income"] == 6000 and s["income_pending"] == 0
