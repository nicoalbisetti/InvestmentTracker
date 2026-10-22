from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from app.expenses.db import ExpBase, create_expense_tables
from app.expenses.models import ExpCategory, ExpEntity


def test_tables_created(engine):
    names = set(inspect(engine).get_table_names())
    assert {t.name for t in ExpBase.metadata.sorted_tables} <= names
    assert all(n.startswith("exp_") for n in names)


def test_seed_idempotent(engine, db):
    before = (db.query(ExpEntity).count(), db.query(ExpCategory).count(),
              [c.id for c in db.query(ExpCategory).order_by(ExpCategory.id)])
    create_expense_tables([engine])
    create_expense_tables([engine])
    db.expire_all()
    after = (db.query(ExpEntity).count(), db.query(ExpCategory).count(),
             [c.id for c in db.query(ExpCategory).order_by(ExpCategory.id)])
    assert before == after
    assert before[0] == 3
    system = {c.name for c in db.query(ExpCategory).filter_by(is_system=True)}
    assert system == {"Tarjeta sin detalle", "Sin clasificar"}


def test_no_foreign_keys_to_investment_tables():
    for t in ExpBase.metadata.sorted_tables:
        for fk in t.foreign_keys:
            assert fk.column.table.name.startswith("exp_"), (t.name, fk.target_fullname)


def test_batch_unique_account_hash(db):
    from datetime import date
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.expenses.models import ExpAccount, ExpImportBatch
    acc = ExpAccount(name="a", institution="x", country="BR", kind="bank", currency="BRL")
    db.add(acc); db.commit()
    mk = lambda: ExpImportBatch(account_id=acc.id, file_hash="h", parser_key="p")
    db.add(mk()); db.commit()
    db.add(mk())
    with pytest.raises(IntegrityError):
        db.commit()
