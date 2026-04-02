"""
Migration script for fixed income import feature.
Adds new columns to instruments and monthly_positions tables,
and recreates monthly_positions with the new UNIQUE constraint.

Run from the backend directory:
    python3 migrate_fixed_income.py
"""
import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "investment_tracker.db")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Run the app first to create it.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Starting fixed income migration...")

    # ── 1. instruments: add new columns ──────────────────────────────────────
    new_instrument_cols = [
        ("ticker",         "TEXT"),
        ("issue_date",     "DATE"),
        ("index_type",     "TEXT"),
        ("in_liquidation", "BOOLEAN DEFAULT 0"),
        ("asset_class",    "TEXT"),
    ]
    for col_name, col_def in new_instrument_cols:
        if not column_exists(cursor, "instruments", col_name):
            cursor.execute(f"ALTER TABLE instruments ADD COLUMN {col_name} {col_def}")
            print(f"  ✓ instruments.{col_name} added")
        else:
            print(f"  - instruments.{col_name} already exists, skipping")

    # ── 2. monthly_positions: recreate with new schema ──────────────────────
    # SQLite doesn't support DROP CONSTRAINT, so we recreate the table.
    cursor.execute("PRAGMA table_info(monthly_positions)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    needs_recreation = "custodian_override" not in existing_cols

    if needs_recreation:
        print("  Recreating monthly_positions table with new schema...")
        cursor.executescript("""
            BEGIN;

            CREATE TABLE monthly_positions_new (
                id                  INTEGER PRIMARY KEY,
                instrument_id       INTEGER NOT NULL REFERENCES instruments(id),
                date                DATE    NOT NULL,
                balance_brl         REAL,
                balance_usd         REAL,
                usd_rate            REAL,
                applications        REAL,
                redemptions         REAL,
                calculated_balance  REAL,
                previous_balance    REAL,
                gain                REAL,
                gain_pct            REAL,
                proventos           REAL,
                avg_price           REAL,
                quantity            REAL,
                unit_price          REAL,
                custodian_override  TEXT,
                capital_invested    REAL,
                UNIQUE(instrument_id, date, custodian_override)
            );

            INSERT INTO monthly_positions_new
                (id, instrument_id, date, balance_brl, balance_usd, usd_rate,
                 applications, redemptions, calculated_balance, previous_balance,
                 gain, gain_pct, proventos, avg_price,
                 quantity, unit_price, custodian_override, capital_invested)
            SELECT
                id, instrument_id, date, balance_brl, balance_usd, usd_rate,
                applications, redemptions, calculated_balance, previous_balance,
                gain, gain_pct, proventos, avg_price,
                NULL, NULL, NULL, NULL
            FROM monthly_positions;

            DROP TABLE monthly_positions;
            ALTER TABLE monthly_positions_new RENAME TO monthly_positions;

            CREATE INDEX IF NOT EXISTS ix_monthly_positions_instrument_id
                ON monthly_positions(instrument_id);
            CREATE INDEX IF NOT EXISTS ix_monthly_positions_date
                ON monthly_positions(date);

            COMMIT;
        """)
        print("  ✓ monthly_positions recreated with new schema")
    else:
        # Just add any missing columns individually
        new_mp_cols = [
            ("quantity",           "REAL"),
            ("unit_price",         "REAL"),
            ("custodian_override", "TEXT"),
            ("capital_invested",   "REAL"),
        ]
        for col_name, col_def in new_mp_cols:
            if not column_exists(cursor, "monthly_positions", col_name):
                cursor.execute(f"ALTER TABLE monthly_positions ADD COLUMN {col_name} {col_def}")
                print(f"  ✓ monthly_positions.{col_name} added")
            else:
                print(f"  - monthly_positions.{col_name} already exists, skipping")

    # ── 3. instrument_code_mappings: create if not exists ───────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS instrument_code_mappings (
            id           INTEGER PRIMARY KEY,
            codigo_excel TEXT    NOT NULL UNIQUE,
            instrument_id INTEGER NOT NULL REFERENCES instruments(id),
            created_at   TEXT    DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_icm_codigo ON instrument_code_mappings(codigo_excel)")
    print("  ✓ instrument_code_mappings ready")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")


if __name__ == "__main__":
    run_migration()
