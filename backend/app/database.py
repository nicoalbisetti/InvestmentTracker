from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from fastapi import Request
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./investment_tracker.db")
DEMO_DATABASE_URL = os.getenv("DEMO_DATABASE_URL", "sqlite:///./investment_tracker_demo.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
demo_engine = create_engine(DEMO_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
DemoSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=demo_engine)


class Base(DeclarativeBase):
    pass


def get_db(request: Request):
    env = request.headers.get("X-Env", "production")
    db = DemoSessionLocal() if env == "demo" else SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_provento_items(eng):
    """Replace the overly-strict unique constraint on provento_items."""
    from sqlalchemy import text
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='provento_items'"
        )).fetchone()
        if row and 'uq_provento_item_inst_date_type_amount' not in row[0]:
            conn.execute(text("""
                CREATE TABLE provento_items_new (
                    id INTEGER NOT NULL,
                    instrument_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    amount_brl FLOAT NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    notes TEXT,
                    quantity FLOAT,
                    unit_price FLOAT,
                    custodian VARCHAR(50),
                    source VARCHAR(50),
                    import_batch_id VARCHAR(36),
                    raw_event_type TEXT,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_provento_item_inst_date_type_amount
                        UNIQUE (instrument_id, date, type, amount_brl),
                    FOREIGN KEY(instrument_id) REFERENCES instruments (id)
                )
            """))
            conn.execute(text("INSERT INTO provento_items_new SELECT * FROM provento_items"))
            conn.execute(text("DROP TABLE provento_items"))
            conn.execute(text("ALTER TABLE provento_items_new RENAME TO provento_items"))
            conn.execute(text("CREATE INDEX ix_provento_items_id ON provento_items (id)"))
            conn.execute(text("CREATE INDEX ix_provento_items_instrument_id ON provento_items (instrument_id)"))
            conn.execute(text("CREATE INDEX ix_provento_items_import_batch_id ON provento_items (import_batch_id)"))
            conn.commit()


def _migrate_return_source(eng):
    """Add return_source column to instruments if it doesn't exist."""
    from sqlalchemy import text
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='instruments'"
        )).fetchone()
        if row and 'return_source' not in row[0]:
            try:
                conn.execute(text("ALTER TABLE instruments ADD COLUMN return_source TEXT"))
                conn.commit()
            except Exception:
                pass


def create_tables():
    # Import all models so Base knows about them
    from app.models import (  # noqa: F401
        instrument,
        monthly_position,
        portfolio_snapshot,
        annual_summary,
        provento,
        provento_forecast,
        provento_item,
        quote,
        transaction,
        import_log,
        instrument_code_mapping,
        market_rate,
        equity_trade,
    )
    Base.metadata.create_all(bind=engine)
