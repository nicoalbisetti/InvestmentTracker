from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./investment_tracker.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    # Import all models so Base knows about them
    from app.models import (  # noqa: F401
        instrument,
        monthly_position,
        portfolio_snapshot,
        annual_summary,
        provento,
        quote,
        transaction,
        import_log,
    )
    Base.metadata.create_all(bind=engine)
