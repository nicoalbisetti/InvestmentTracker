"""Migraciones ad-hoc de la base de gastos (mismo patrón _migrate_* que app.database).

Las tablas nuevas las crea create_all; acá van sólo cambios sobre tablas existentes.
"""


ADDED_COLUMNS = {
    "exp_rules": [("set_needs_review", "BOOLEAN NOT NULL DEFAULT 0"), ("set_counterparty_account_id", "INTEGER"),
                  ("set_exclude_from_audit", "BOOLEAN NOT NULL DEFAULT 0")],
    "exp_transactions": [("counterparty_account_id", "INTEGER"), ("exclude_from_audit", "BOOLEAN NOT NULL DEFAULT 0")],
    "exp_accounts": [("itemizes_investments", "BOOLEAN NOT NULL DEFAULT 0")],
}


def run_migrations(eng):
    """Columnas agregadas después de la primera versión (idempotente)."""
    from sqlalchemy import text
    with eng.connect() as conn:
        for table, cols in ADDED_COLUMNS.items():
            have = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))]
            if not have:
                continue
            for name, ddl in cols:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        conn.commit()
