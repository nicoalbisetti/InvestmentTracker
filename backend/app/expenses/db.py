import os

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

EXP_DATABASE_URL = os.getenv("EXPENSES_DATABASE_URL", "sqlite:///./expenses.db")
EXP_DEMO_DATABASE_URL = os.getenv("EXPENSES_DEMO_DATABASE_URL", "sqlite:///./expenses_demo.db")

exp_engine = create_engine(EXP_DATABASE_URL, connect_args={"check_same_thread": False})
exp_demo_engine = create_engine(EXP_DEMO_DATABASE_URL, connect_args={"check_same_thread": False})

ExpSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=exp_engine)
ExpDemoSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=exp_demo_engine)


class ExpBase(DeclarativeBase):
    pass


def get_exp_db(request: Request):
    env = request.headers.get("X-Env", "production")
    db = ExpDemoSessionLocal() if env == "demo" else ExpSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_expense_tables(engines=None, with_demo=True):
    """create_all + seeds idempotentes en la base real y en la demo. La demo se llena con datos ficticios
    la primera vez (si no tiene cuentas)."""
    from app.expenses import models  # noqa: F401  (registra tablas)
    from app.expenses.migrations import run_migrations
    from app.expenses.seed.base import seed_base_data
    from app.expenses.services.rules import EXAMPLE_RULES, load_seed_rules

    for eng in engines or (exp_engine, exp_demo_engine):
        ExpBase.metadata.create_all(bind=eng)
        run_migrations(eng)
        with sessionmaker(bind=eng)() as db:
            seed_base_data(db)
            # la demo NUNCA carga las reglas locales (tienen nombres reales): sólo el ejemplo
            load_seed_rules(db, EXAMPLE_RULES) if eng is exp_demo_engine else load_seed_rules(db)
            if with_demo and eng is exp_demo_engine:
                from app.expenses.models import ExpAccount
                if db.query(ExpAccount).count() == 0:
                    from app.expenses.seed.demo import seed_demo
                    seed_demo(db)
