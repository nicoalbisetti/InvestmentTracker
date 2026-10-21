import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.expenses.db import create_expense_tables


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    create_expense_tables([eng])
    return eng


@pytest.fixture
def db(engine):
    with sessionmaker(bind=engine)() as session:
        yield session
