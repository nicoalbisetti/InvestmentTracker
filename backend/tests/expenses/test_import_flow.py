import pytest

from tests.expenses.conftest import FIX
from app.expenses.models import ExpAccount, ExpImportBatch, ExpTransaction


def mk_account(client, **kw):
    body = dict(name="Cuenta", institution="X", country="BR", kind="bank", currency="BRL")
    body.update(kw)
    r = client.post("/api/expenses/accounts", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(client, path, name=None, **data):
    return client.post("/api/expenses/imports", files={"file": (name or path.name, path.read_bytes())}, data=data)


@pytest.fixture
def card(client):
    return mk_account(client, name="Tarjeta XP", kind="credit_card", parser_key="xp_card_csv")


@pytest.fixture
def inter(client):
    return mk_account(client, name="Inter", parser_key="inter_account_csv", owner_identifiers=["titular ficticio"])


CARD = FIX / "xp_card_sample_Fatura2026-03-20.csv"
INTER = FIX / "inter_account_sample.csv"


def test_preview_confirm_card_and_reimport_409(client, db, card):
    r = upload(client, CARD)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "preview" and body["rows_total"] == 8 and body["rows_new"] == 8
    assert all(c["ok"] for c in body["validation"])
    assert body["statement_period"] == "2026-03"
    row = next(x for x in body["rows"] if x["description_raw"] == "ESTORNO COMERCIO")
    assert row["kind"] == "refund" and row["amount"] == 7.0
    pay = next(x for x in body["rows"] if x["kind"] == "card_payment")
    assert pay["amount"] == 50.0 and not pay["needs_review"]

    c = client.post(f"/api/expenses/imports/{body['id']}/confirm", json={})
    assert c.status_code == 200 and c.json()["rows_new"] == 8 and c.json()["status"] == "confirmed"
    assert db.query(ExpTransaction).count() == 8
    easy = db.query(ExpTransaction).filter(ExpTransaction.description_raw.like("EASYJET%")).all()
    assert len(easy) == 3 and sum(1 for t in easy if t.amount == -10.0) == 2
    assert all(t.amount_brl is not None and t.amount_usd is not None for t in db.query(ExpTransaction))
    # consumo en cuotas: fecha = vencimiento, compra original conservada
    inst = db.query(ExpTransaction).filter_by(description_raw="LOJA EXEMPLO").one()
    assert (inst.installment_number, str(inst.date), str(inst.purchase_date)) == (3, "2026-03-20", "2025-12-10")

    again = upload(client, CARD)
    assert again.status_code == 409


def test_nothing_persisted_before_confirm(client, db, card):
    upload(client, CARD)
    assert db.query(ExpTransaction).count() == 0


def test_overlapping_export_inserts_only_new_rows(client, db, inter, tmp_path):
    b1 = upload(client, INTER).json()
    client.post(f"/api/expenses/imports/{b1['id']}/confirm", json={})
    extended = INTER.read_text().rstrip("\n") + '\n06/01/2026;Pix enviado: "Cp :11111111-Titular Ficticio";-10,00;100,00\n'
    f = tmp_path / "inter_extended.csv"; f.write_text(extended)
    b2 = upload(client, f).json()
    assert (b2["rows_total"], b2["rows_new"], b2["rows_duplicate"]) == (5, 1, 4)
    client.post(f"/api/expenses/imports/{b2['id']}/confirm", json={})
    assert db.query(ExpTransaction).count() == 5


def test_delete_confirmed_batch_removes_exactly_its_rows(client, db, card, inter):
    b1 = upload(client, CARD).json(); client.post(f"/api/expenses/imports/{b1['id']}/confirm", json={})
    b2 = upload(client, INTER).json(); client.post(f"/api/expenses/imports/{b2['id']}/confirm", json={})
    assert db.query(ExpTransaction).count() == 12
    r = client.delete(f"/api/expenses/imports/{b1['id']}")
    assert r.json()["deleted_rows"] == 8
    db.expire_all()
    assert db.query(ExpTransaction).count() == 4
    assert {t.batch_id for t in db.query(ExpTransaction)} == {b2["id"]}
    assert upload(client, CARD).status_code == 200  # se puede reimportar tras borrar


def test_failing_validation_blocks_confirm_unless_force(client, inter, tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text(INTER.read_text().replace("1.150,00", "1.151,00"))
    b = upload(client, f).json()
    assert any(not c["ok"] for c in b["validation"])
    assert client.post(f"/api/expenses/imports/{b['id']}/confirm", json={}).status_code == 422
    assert client.post(f"/api/expenses/imports/{b['id']}/confirm", json={"force": True}).status_code == 200


def test_due_date_required_when_not_in_filename(client, card):
    r = upload(client, CARD, name="export.csv")
    assert r.status_code == 422 and r.json()["detail"]["needs_due_date"]
    ok = upload(client, CARD, name="export.csv", due_date="2026-04-20")
    assert ok.status_code == 200 and ok.json()["statement_period"] == "2026-04"


def test_account_must_be_chosen_when_ambiguous(client):
    mk_account(client, parser_key="inter_account_csv", name="A")
    mk_account(client, parser_key="inter_account_csv", name="B")
    r = upload(client, INTER)
    assert r.status_code == 422 and len(r.json()["detail"]["candidates"]) == 2


def test_unknown_format(client, tmp_path):
    f = tmp_path / "x.csv"; f.write_text("a,b\n1,2\n")
    assert upload(client, f).status_code == 422


def test_overrides_are_manual_and_survive(client, db, inter):
    b = upload(client, INTER).json()
    cat = client.get("/api/expenses/accounts").status_code  # sanity
    assert cat == 200
    client.post(f"/api/expenses/imports/{b['id']}/confirm",
                json={"overrides": [{"index": 1, "kind": "income"}]})
    t = db.query(ExpTransaction).order_by(ExpTransaction.id).all()[1]
    assert t.kind == "income" and t.classification_source == "manual" and not t.needs_review


def test_file_name_not_persisted(client, db, card):
    upload(client, CARD, name="Fatura2026-03-20_00000000000000000000.csv")
    b = db.query(ExpImportBatch).one()
    assert "0072" not in (b.file_label or "")
