import pytest
from fastapi.testclient import TestClient

from app.expenses import db as expdb
from app.main import app


@pytest.fixture
def client(engine):
    from sqlalchemy.orm import sessionmaker
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


def test_accounts_endpoint_empty(client):
    r = client.get("/api/expenses/accounts")
    assert r.status_code == 200 and r.json() == []


def test_manual_rate_roundtrip(client):
    body = {"pair": "USDBRL_PTAX", "date": "2026-04-02", "rate": 5.5}
    assert client.put("/api/expenses/fx/rates", json=body).status_code == 200
    r = client.get("/api/expenses/fx/rates", params={"pair": "USDBRL_PTAX", "date_from": "2026-04-01", "date_to": "2026-04-30"})
    assert r.json() == [{"date": "2026-04-02", "rate": 5.5, "source": "manual"}]
    assert client.put("/api/expenses/fx/rates", json={**body, "pair": "X"}).status_code == 422
