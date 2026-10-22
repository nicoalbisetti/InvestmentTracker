from datetime import date

from app.expenses.models import ExpAccount, ExpCategory, ExpFxRate, ExpImportBatch, ExpRule, ExpTransaction
from app.expenses.services import fx, installments

D = date
_n = [0]


def cat(db, name):
    return db.query(ExpCategory).filter_by(name=name).one().id


# ---------- reglas: editar / borrar / reordenar ----------
def test_patch_rule_validates_and_flips_seed_to_manual(client, db):
    seed = db.query(ExpRule).filter_by(origin="seed").first()
    r = client.patch(f"/api/expenses/rules/{seed.id}", json={"set_category_id": cat(db, "Otros"), "active": False})
    assert r.status_code == 200 and r.json()["origin"] == "manual" and r.json()["active"] is False
    assert client.patch(f"/api/expenses/rules/{seed.id}", json={"pattern": "("}).status_code == 422
    assert client.patch(f"/api/expenses/rules/{seed.id}", json={"set_kind": "nope"}).status_code == 422
    assert client.patch("/api/expenses/rules/99999", json={"active": True}).status_code == 404
    # una regla editada deja de ser pisada al recargar las semillas
    from app.expenses.services.rules import load_seed_rules
    load_seed_rules(db)
    db.expire_all()
    assert db.get(ExpRule, seed.id).active is False


def test_patch_rule_can_apply_to_pending(client, db):
    a = ExpAccount(name="A", institution="X", country="BR", kind="bank", currency="BRL"); db.add(a); db.commit()
    t = ExpTransaction(account_id=a.id, date=D(2026, 1, 1), description_raw="PADARIA", merchant_normalized="PADARIA", amount=-5,
                       amount_brl=-5, currency="BRL", kind="expense", needs_review=True, dedup_hash="p1")
    db.add(t)
    rule = ExpRule(pattern="PADARIA", field="merchant_normalized", set_kind="expense", origin="manual", active=False)
    db.add(rule); db.commit()
    r = client.patch(f"/api/expenses/rules/{rule.id}", json={"active": True, "set_category_id": cat(db, "Otros"), "apply_to_pending": True})
    assert r.json()["applied"] == 1
    db.expire_all()
    assert t.category_id == cat(db, "Otros") and not t.needs_review


def test_delete_rule_manual_only_and_detaches_rows(client, db):
    seed = db.query(ExpRule).filter_by(origin="seed").first()
    assert client.delete(f"/api/expenses/rules/{seed.id}").status_code == 409
    a = ExpAccount(name="A", institution="X", country="BR", kind="bank", currency="BRL"); db.add(a); db.commit()
    rule = ExpRule(pattern="X", field="description_raw", set_kind="expense", origin="manual"); db.add(rule); db.commit()
    t = ExpTransaction(account_id=a.id, date=D(2026, 1, 1), description_raw="X", amount=-1, amount_brl=-1, currency="BRL",
                       kind="expense", rule_id=rule.id, classification_source="rule", dedup_hash="d1")
    db.add(t); db.commit()
    rid = rule.id
    assert client.delete(f"/api/expenses/rules/{rid}").json() == {"deleted": rid}
    db.expire_all()
    assert t.rule_id is None and t.kind == "expense"          # la clasificación queda, sólo se desvincula
    assert client.delete(f"/api/expenses/rules/{rid}").status_code == 404


def test_reorder_moves_only_what_changes(client, db):
    ids = [r["id"] for r in client.get("/api/expenses/rules").json()]
    before = {r["id"]: (r["priority"], r["origin"]) for r in client.get("/api/expenses/rules").json()}
    same = client.post("/api/expenses/rules/reorder", json={"ids": ids}).json()
    assert same == {"moved": 0}                                # mismo orden: nada cambia ni se marca manual
    new = [ids[1], ids[0]] + ids[2:]                           # intercambia las dos primeras
    assert client.post("/api/expenses/rules/reorder", json={"ids": new}).json() == {"moved": 2}
    after = {r["id"]: r for r in client.get("/api/expenses/rules").json()}
    assert after[ids[1]]["priority"] == before[ids[0]][0] and after[ids[0]]["priority"] == before[ids[1]][0]
    assert after[ids[2]]["origin"] == before[ids[2]][1]        # las que no se movieron siguen igual
    assert [r["id"] for r in client.get("/api/expenses/rules").json()][:2] == [ids[1], ids[0]]
    assert client.post("/api/expenses/rules/reorder", json={"ids": ids[:-1]}).status_code == 422
    assert client.post("/api/expenses/rules/reorder", json={"ids": ids + [ids[0]]}).status_code == 422


# ---------- tipos de cambio ----------
def test_delete_manual_rate_restores_source(client, db):
    pair, d = "USDBRL_PTAX", D(2026, 4, 2)
    fx.refresh(db, d, d, pairs=(pair,))                         # valor de la fuente (stub de tests: 5.0)
    fx.set_manual_rate(db, pair, d, 9.99)
    assert client.delete("/api/expenses/fx/rates", params={"pair": pair, "date": "2026-04-02"}).json()["restored"] is True
    db.expire_all()
    row = db.get(ExpFxRate, (d, pair))
    assert row.rate == 5.0 and row.source == "ptax"
    assert client.delete("/api/expenses/fx/rates", params={"pair": pair, "date": "2026-04-02"}).status_code == 404


# ---------- cuotas comprometidas ----------
def _card(db, name="Tarjeta"):
    a = ExpAccount(name=name, institution="X", country="BR", kind="credit_card", currency="BRL"); db.add(a); db.commit()
    return a


def _statement(db, acc, due, rows):
    _n[0] += 1
    b = ExpImportBatch(account_id=acc.id, file_hash=f"h{_n[0]}", parser_key="p", status="confirmed", statement_due_date=due,
                       statement_period=due.strftime("%Y-%m")); db.add(b); db.commit()
    for desc, amt, n, total in rows:
        _n[0] += 1
        db.add(ExpTransaction(account_id=acc.id, batch_id=b.id, date=due, description_raw=desc, amount=amt, amount_brl=amt, currency="BRL",
                              kind="expense", installment_number=n, installment_total=total, dedup_hash=f"i{_n[0]}"))
    db.commit()
    return b


def test_upcoming_installments_from_last_statement_only(db):
    a = _card(db)
    _statement(db, a, D(2026, 5, 20), [("VIEJA", -50.0, 1, 3)])                       # fatura vieja: no cuenta
    _statement(db, a, D(2026, 6, 20), [("TV", -100.0, 2, 4), ("SOFA", -300.0, 5, 6), ("CONTADO", -80.0, None, None),
                                      ("ULTIMA", -40.0, 3, 3)])
    r = installments.upcoming(db, months=6, today=D(2026, 7, 1))
    months = {m["month"]: m for m in r["months"]}
    assert sorted(months) == ["2026-07", "2026-08"]
    assert months["2026-07"]["total_brl"] == 400.0 and months["2026-08"]["total_brl"] == 100.0   # TV 3/4 y 4/4; SOFA 6/6
    assert [(i["merchant"], i["installment"], i["of"]) for i in months["2026-07"]["items"]] == [("SOFA", 6, 6), ("TV", 3, 4)]
    assert r["cards"] == [{"account_id": a.id, "name": "Tarjeta", "last_statement_due": "2026-06-20", "stale": False}]


def test_upcoming_limits_months_flags_stale_and_ignores_cards_without_statements(db):
    a = _card(db)
    ExpAccount(name="Sin fatura", institution="X", country="BR", kind="credit_card", currency="BRL", has_statements=False)
    _statement(db, a, D(2026, 1, 20), [("HEAVY", -10.0, 1, 12)])
    r = installments.upcoming(db, months=3, today=D(2026, 10, 22))
    assert [m["month"] for m in r["months"]] == ["2026-02", "2026-03", "2026-04"] and r["cards"][0]["stale"] is True


def test_upcoming_endpoint(client, db):
    a = _card(db); _statement(db, a, D(2026, 6, 20), [("TV", -100.0, 1, 3)])
    r = client.get("/api/expenses/installments/upcoming", params={"months": 6}).json()
    assert [m["month"] for m in r["months"]] == ["2026-07", "2026-08"]
    assert client.get("/api/expenses/installments/upcoming", params={"months": 0}).status_code == 422
