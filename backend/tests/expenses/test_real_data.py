"""Verificación contra los extractos reales (se saltea si faltan). Los valores esperados y las
identidades propias viven en real_golden.json, que no se commitea."""
import json
import pathlib

import pytest

from app.expenses.models import ExpAccount, ExpTransaction
from app.expenses.services import importer, linking

REAL = pathlib.Path(__file__).resolve().parents[3] / "docs" / "expenses"
GOLDEN = pathlib.Path(__file__).parent / "real_golden.json"

pytestmark = pytest.mark.skipif(not (REAL.exists() and GOLDEN.exists()), reason="datos reales no disponibles")


def test_br_import_pairs_and_invoices(db):
    g = json.loads(GOLDEN.read_text())
    mk = lambda **k: (db.add(ExpAccount(institution="x", country="BR", currency="BRL", **k)), db.commit())
    mk(name="xp", kind="bank", parser_key="xp_account_csv", owner_identifiers=g["owner_identifiers"])
    mk(name="xpcard", kind="credit_card", parser_key="xp_card_csv", paid_from_account_id=1)
    mk(name="inter", kind="bank", parser_key="inter_account_csv", owner_identifiers=g["owner_identifiers"])
    for f in sorted(REAL.glob("*.csv")):
        b = importer.create_preview(db, f.read_bytes(), f.name)
        importer.confirm(db, b["id"])
    exp = g["br_linking"]
    inter_paired = db.query(ExpTransaction).filter(
        ExpTransaction.account_id == 3, ExpTransaction.transfer_group_id.isnot(None)).count()
    assert inter_paired == exp["inter_paired_rows"]
    pay = linking.payer_card_payments(db)
    assert sum(1 for t in pay if linking.is_exact_statement_link(db, t)) == exp["xp_invoices_linked_exact"]
    assert sum(1 for t in pay if t.statement_batch_id is None) == exp["payer_payments_without_statement"]
    with pytest.raises(importer.ImportError_) as e:
        f = sorted(REAL.glob("*.csv"))[0]
        importer.create_preview(db, f.read_bytes(), f.name)
    assert e.value.status == 409
