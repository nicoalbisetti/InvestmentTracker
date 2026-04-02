"""
Migración idempotente: crea la tabla equity_trades si no existe.
Ejecutar: python backend/migrations/add_equity_trades.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.database import engine


def run():
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='equity_trades'")
        ).fetchone()

        if existing:
            print("Tabla equity_trades ya existe — sin cambios.")
            return

        conn.execute(text("""
            CREATE TABLE equity_trades (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                instrument_id INTEGER NOT NULL REFERENCES instruments(id),
                date DATE NOT NULL,
                trade_type VARCHAR(10) NOT NULL,
                quantity FLOAT NOT NULL,
                price FLOAT NOT NULL,
                amount_brl FLOAT,
                notes TEXT,
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("CREATE INDEX ix_equity_trades_instrument_id ON equity_trades (instrument_id)"))
        conn.execute(text("CREATE INDEX ix_equity_trades_date ON equity_trades (date)"))
        conn.commit()
        print("Tabla equity_trades creada exitosamente.")


if __name__ == "__main__":
    run()
