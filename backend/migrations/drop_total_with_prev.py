"""
Migración idempotente: elimina total_with_prev y total_usd_with_prev de portfolio_snapshots.
Ejecutar: python backend/migrations/drop_total_with_prev.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.database import engine


def run():
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info(portfolio_snapshots)")).fetchall()
        col_names = [c[1] for c in cols]

        if "total_with_prev" not in col_names and "total_usd_with_prev" not in col_names:
            print("Columnas ya eliminadas — sin cambios.")
            return

        keep = [c for c in col_names if c not in ("total_with_prev", "total_usd_with_prev")]
        keep_str = ", ".join(keep)

        conn.execute(text(f"""
            CREATE TABLE portfolio_snapshots_new AS
            SELECT {keep_str} FROM portfolio_snapshots
        """))
        conn.execute(text("DROP TABLE portfolio_snapshots"))
        conn.execute(text("ALTER TABLE portfolio_snapshots_new RENAME TO portfolio_snapshots"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_portfolio_snapshots_date ON portfolio_snapshots (date)"))
        conn.commit()
        print("Columnas total_with_prev y total_usd_with_prev eliminadas.")


if __name__ == "__main__":
    run()
