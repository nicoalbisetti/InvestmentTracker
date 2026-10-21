import pathlib
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.expenses import db as expdb
from app.expenses.db import create_expense_tables
from app.expenses.services import fx

FIX = pathlib.Path(__file__).parent / "fixtures"
EXAMPLE_RULES = pathlib.Path(__file__).resolve().parents[2] / "app" / "expenses" / "seed" / "rules.example.json"


@pytest.fixture(autouse=True)
def _example_rules_and_no_network(monkeypatch):
    """Tests deterministas: reglas de ejemplo (no las locales) y FX sin red."""
    monkeypatch.setenv("EXPENSES_RULES_FILE", str(EXAMPLE_RULES))

    def fake(url):
        if "olinda" in url:
            d, rows = date(2025, 11, 1), []
            while d <= date(2026, 12, 31):
                if d.weekday() < 5:
                    rows.append({"cotacaoVenda": 5.0, "dataHoraCotacao": f"{d.isoformat()} 13:00:00.0"})
                d += timedelta(days=1)
            return {"value": rows}
        return [{"casa": "bolsa", "compra": 1000.0, "venta": 1000.0, "fecha": "2026-01-01"}]

    monkeypatch.setattr(fx, "_http_get_json", fake)


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    create_expense_tables([eng])
    return eng


@pytest.fixture
def db(engine):
    with sessionmaker(bind=engine)() as session:
        yield session


@pytest.fixture
def client(engine):
    from app.main import app
    Session = sessionmaker(bind=engine)

    def override(request=None):
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[expdb.get_exp_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def inv_engine():
    """Base de inversiones en memoria (esquema real) para probar la conciliación."""
    from app.database import Base
    from app.models import (  # noqa: F401  (registra todas las tablas y relaciones)
        instrument, monthly_position, portfolio_snapshot, annual_summary, provento, provento_forecast,
        provento_item, quote, transaction, import_log, instrument_code_mapping, market_rate, equity_trade)
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def inv(inv_engine):
    with sessionmaker(bind=inv_engine)() as session:
        yield session


@pytest.fixture
def client_inv(engine, inv_engine):
    """Cliente con ambas bases (gastos e inversiones) reemplazadas por las de prueba."""
    from app.main import app
    from app.expenses.services import linking
    ExpS, InvS = sessionmaker(bind=engine), sessionmaker(bind=inv_engine)

    def exp_override(request=None):
        s = ExpS()
        try:
            yield s
        finally:
            s.close()

    def inv_override(request=None):
        s = InvS()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[expdb.get_exp_db] = exp_override
    app.dependency_overrides[linking.get_inv_db] = inv_override
    yield TestClient(app)
    app.dependency_overrides.clear()
