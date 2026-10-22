from datetime import date

import pytest

from app.expenses.models import ExpAccount, ExpLink, ExpTransaction
from app.expenses.services import linking, review
from app.models.instrument import Instrument
from app.models.provento_item import ProvéntoItem
from app.models.transaction import Transaction

D = date
_n = [0]


def bank(db, d, amount, kind, desc="movimiento", **kw):
    if not db.query(ExpAccount).count():
        db.add(ExpAccount(name="Banco", institution="XP", country="BR", kind="bank", currency="BRL", itemizes_investments=True)); db.commit()
    _n[0] += 1
    t = ExpTransaction(account_id=1, date=d, description_raw=desc, amount=amount, currency="BRL", amount_brl=amount,
                       amount_usd=amount / 5, kind=kind, dedup_hash=f"i{_n[0]}", **kw)
    db.add(t); db.commit()
    return t


def instrument(inv, name, custodian="XP", in_liq=False):
    i = Instrument(name=name, custodian=custodian, in_liquidation=in_liq)
    inv.add(i); inv.commit()
    return i


def inv_tx(inv, i, d, amount, type_):
    t = Transaction(instrument_id=i.id, date=d, type=type_, amount_brl=amount)
    inv.add(t); inv.commit()
    return t


def prov(inv, i, d, amount, custodian=None):
    p = ProvéntoItem(instrument_id=i.id, date=d, amount_brl=amount, type="dividendo", custodian=custodian)
    inv.add(p); inv.commit()
    return p


def links(db, **f):
    return db.query(ExpLink).filter_by(**f).all()


# ---------- aportes / rescates ----------
def test_contribution_matches_application_and_is_only_suggested(db, inv):
    i = instrument(inv, "CDB Uno")
    t = inv_tx(inv, i, D(2026, 3, 5), 10000.00, "aplicacion")
    e = bank(db, D(2026, 3, 20), -10000.00, "investment_contribution")
    assert linking.link_investments(db, inv) == 1
    (l,) = links(db)
    assert (l.exp_transaction_id, l.target_id, l.status, l.link_type) == (e.id, t.id, "suggested", "investment")
    assert l.target_label == "CDB Uno" and l.amount_allocated_brl == 10000.00 and 0 < l.score <= 1
    assert linking.link_investments(db, inv) == 0  # idempotente


def test_far_or_different_amount_or_wrong_type_not_suggested(db, inv):
    i = instrument(inv, "CDB")
    inv_tx(inv, i, D(2026, 1, 1), 10000.00, "aplicacion")          # 79 días
    inv_tx(inv, i, D(2026, 3, 20), 10200.00, "aplicacion")         # 2 % de diferencia
    inv_tx(inv, i, D(2026, 3, 20), 10000.00, "rescate")            # tipo opuesto
    bank(db, D(2026, 3, 20), -10000.00, "investment_contribution")
    assert linking.link_investments(db, inv) == 0


def test_one_transaction_is_not_assigned_to_two_bank_movements(db, inv):
    i = instrument(inv, "CDB")
    inv_tx(inv, i, D(2026, 3, 5), 500.00, "aplicacion")
    bank(db, D(2026, 3, 5), -500.00, "investment_contribution")
    bank(db, D(2026, 3, 6), -500.00, "investment_contribution")
    assert linking.link_investments(db, inv) == 1


def test_fgc_one_transfer_explains_two_redemptions_within_6_percent_only_in_liquidation(db, inv):
    a = instrument(inv, "Will 2027", in_liq=True); b = instrument(inv, "Will 2028", in_liq=True)
    other = instrument(inv, "CDB normal", in_liq=False)
    inv_tx(inv, a, D(2026, 4, 8), 50000.00, "rescate"); inv_tx(inv, b, D(2026, 4, 8), 50000.00, "rescate")
    inv_tx(inv, other, D(2026, 4, 8), 103059.68, "rescate")      # exacto, pero no está en liquidación
    e = bank(db, D(2026, 4, 8), 103059.68, "investment_withdrawal", desc="TED FUNDO GARANTIDOR DE CREDITOS")
    linking.link_investments(db, inv)
    labels = sorted(l.target_label for l in links(db, exp_transaction_id=e.id))
    assert labels == ["Will 2027", "Will 2028"]                    # 100.000 vs 103.059,68: 3 % -> dentro del 6 %
    g = linking.suggestions(db)[0]
    assert g["difference_brl"] == pytest.approx(-3059.68)


def test_non_fgc_does_not_get_the_6_percent_tolerance(db, inv):
    i = instrument(inv, "CDB")
    inv_tx(inv, i, D(2026, 4, 8), 100000.00, "rescate")
    bank(db, D(2026, 4, 8), 103059.68, "investment_withdrawal", desc="TED comum")
    assert linking.link_investments(db, inv) == 0


def test_unpaired_incoming_transfer_can_match_a_redemption_exactly(db, inv):
    i = instrument(inv, "CDB SANT")
    t = inv_tx(inv, i, D(2026, 4, 28), 76594.00, "rescate")
    e = bank(db, D(2026, 4, 29), 76594.00, "own_transfer", desc="Pix recebido de la misma persona")
    assert linking.link_investments(db, inv) == 1 and links(db)[0].target_id == t.id
    bank(db, D(2026, 5, 1), 76594.50, "own_transfer")             # no exacto: no se sugiere
    assert linking.link_investments(db, inv) == 0 and e.kind == "own_transfer"


def test_rejected_pair_is_not_suggested_again_and_confirm_discards_alternatives(db, inv):
    i = instrument(inv, "CDB")
    inv_tx(inv, i, D(2026, 3, 5), 100.00, "aplicacion")
    e1 = bank(db, D(2026, 3, 5), -100.00, "investment_contribution")
    linking.link_investments(db, inv)
    (l,) = links(db)
    linking.set_link_status(db, l.id, "rejected")
    assert linking.link_investments(db, inv) == 0
    # confirmar un vínculo descarta los demás sugeridos para el mismo destino
    db.add(ExpLink(exp_transaction_id=e1.id, target_type="investment_transaction", target_id=l.target_id,
                   link_type="investment", status="suggested"))
    other = ExpLink(exp_transaction_id=e1.id + 99, target_type="investment_transaction", target_id=l.target_id,
                    link_type="investment", status="suggested")
    db.add(other); db.commit()
    mine = [x for x in links(db) if x.status == "suggested" and x.exp_transaction_id == e1.id][0]
    linking.set_link_status(db, mine.id, "confirmed")
    db.refresh(other)
    assert other.status == "rejected"


# ---------- proventos ----------
def test_one_payment_explains_two_proventos_without_custody_filter(db, inv):
    i = instrument(inv, "SunnyHub", custodian="XP")
    p1 = prov(inv, i, D(2026, 5, 10), 600.00, custodian=None); p2 = prov(inv, i, D(2026, 6, 10), 400.00, custodian="OTRO")
    bank(db, D(2026, 6, 12), 1000.00, "provento", desc="Pix SUNNYHUB")
    linking.link_proventos(db, inv)
    assert sorted(l.target_id for l in links(db, link_type="provento")) == sorted([p1.id, p2.id])


def test_two_payments_explain_one_provento(db, inv):
    i = instrument(inv, "VALE3")
    p = prov(inv, i, D(2026, 3, 20), 3950.00)
    bank(db, D(2026, 3, 20), 2458.67, "provento"); bank(db, D(2026, 3, 21), 1491.33, "provento")
    linking.link_proventos(db, inv)
    ls = links(db, link_type="provento")
    assert len(ls) == 2 and {l.target_id for l in ls} == {p.id}
    assert sorted(l.amount_allocated_brl for l in ls) == [1491.33, 2458.67]
    assert all(l.status == "suggested" for l in ls)


def test_unrelated_amount_not_linked(db, inv):
    i = instrument(inv, "X")
    prov(inv, i, D(2026, 3, 20), 100.00)
    bank(db, D(2026, 3, 20), 777.00, "provento")
    assert linking.link_proventos(db, inv) == 0


# ---------- auditoría ----------
def test_audit_reports_the_three_kinds_of_differences(db, inv):
    i = instrument(inv, "CDB A", custodian="XP"); j = instrument(inv, "CDB B", custodian="OTRO BANCO")
    t_ok = inv_tx(inv, i, D(2026, 3, 5), 1000.00, "aplicacion")
    inv_tx(inv, i, D(2026, 3, 9), 2000.00, "aplicacion")              # custodia con cuenta importada y sin movimiento
    inv_tx(inv, j, D(2026, 3, 9), 3000.00, "aplicacion")              # custodia no importada: no se audita
    e_ok = bank(db, D(2026, 3, 5), -1000.00, "investment_contribution")
    bank(db, D(2026, 3, 15), -777.00, "investment_contribution")      # sin transacción
    linking.link_investments(db, inv)
    link = links(db, exp_transaction_id=e_ok.id)[0]
    linking.set_link_status(db, link.id, "confirmed")
    a = linking.audit_investments(db, inv, D(2026, 3, 1), D(2026, 3, 31))
    assert [x["amount"] for x in a["bank_movements_without_transaction"]] == [-777.0]
    assert [x["amount_brl"] for x in a["transactions_without_bank_movement"]] == [2000.0]
    assert a["confirmed_link_differences"] == [] and a["drifted_links"] == []
    # deriva: se edita el monto en inversiones después de confirmar
    t_ok.amount_brl = 1200.00; inv.commit()
    a = linking.audit_investments(db, inv)
    assert len(a["drifted_links"]) == 1


def test_audit_does_not_modify_investments(db, inv):
    i = instrument(inv, "CDB", custodian="XP")
    inv_tx(inv, i, D(2026, 3, 5), 1000.00, "aplicacion")
    before = inv.query(Transaction).count(), inv.query(Instrument).count()
    linking.audit_investments(db, inv); linking.rebuild_investments(db, inv)
    assert before == (inv.query(Transaction).count(), inv.query(Instrument).count())


# ---------- cola de revisión y API ----------
def test_review_queue_lists_unlinked_investment_and_provento_movements(db, inv):
    bank(db, D(2026, 3, 5), -100.00, "investment_contribution"); bank(db, D(2026, 3, 6), 50.00, "provento")
    q = review.review_queue(db)
    assert len(q["investments_unlinked"]) == 1 and len(q["proventos_unlinked"]) == 1


def test_api_flow_rebuild_confirm_reject_audit(client_inv, db, inv):
    i = instrument(inv, "CDB", custodian="XP")
    inv_tx(inv, i, D(2026, 3, 5), 100.00, "aplicacion")
    bank(db, D(2026, 3, 5), -100.00, "investment_contribution")
    r = client_inv.post("/api/expenses/links/rebuild").json()
    assert r["investments"] == 1
    sug = client_inv.get("/api/expenses/links/suggestions").json()
    assert len(sug) == 1 and sug[0]["links"][0]["label"] == "CDB" and sug[0]["difference_brl"] == 0
    lid = sug[0]["links"][0]["id"]
    assert client_inv.post(f"/api/expenses/links/{lid}/confirm").status_code == 200
    assert client_inv.get("/api/expenses/links/suggestions").json() == []
    assert len(client_inv.get("/api/expenses/links/suggestions", params={"status": "confirmed"}).json()) == 1
    assert client_inv.post("/api/expenses/links/9999/reject").status_code == 404
    audit = client_inv.get("/api/expenses/audit/investments", params={"from": "2026-03-01", "to": "2026-03-31"}).json()
    assert audit["bank_movements_without_transaction"] == []
