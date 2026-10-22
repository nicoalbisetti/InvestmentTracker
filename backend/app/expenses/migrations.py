"""Migraciones ad-hoc de la base de gastos (mismo patrón _migrate_* que app.database).

Las tablas nuevas las crea create_all; acá van sólo cambios sobre tablas existentes.
"""


def run_migrations(eng):
    from sqlalchemy import text
    with eng.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(exp_rules)"))]
        if cols and "set_needs_review" not in cols:
            conn.execute(text("ALTER TABLE exp_rules ADD COLUMN set_needs_review BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
