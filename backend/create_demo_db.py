"""
Generate investment_tracker_demo.db with realistic fake positions.

- Instruments, market_rates, quotes: copied as-is (no personal data)
- monthly_positions: fake quantities/balances per instrument type
- portfolio_snapshots, proventos, annual_summaries: recalculated from demo positions

Run from the backend/ directory:
    python create_demo_db.py
"""
import os
import random
import sqlite3
from datetime import date

random.seed(42)

REAL_DB = os.path.join(os.path.dirname(__file__), "investment_tracker.db")
DEMO_DB = os.path.join(os.path.dirname(__file__), "investment_tracker_demo.db")

# Fake balance ranges (BRL) for instruments without unit_price
BALANCE_RANGES = {
    "fundo":       (40_000, 350_000),
    "previdencia": (80_000, 600_000),
    "renta_fija":  (20_000, 280_000),
    "outro":       (10_000, 120_000),
    "saving":      (15_000, 100_000),
    "prestamos":   (10_000,  80_000),
}
DEFAULT_BALANCE_RANGE = (20_000, 200_000)

# Fake quantity ranges for price-based instruments (accion, fii, exterior equity)
QTY_RANGES = {
    "accion": (50, 600),
    "fii":    (100, 1200),
}
DEFAULT_QTY_RANGE = (50, 500)


def connect(path):
    return sqlite3.connect(path)


def copy_table(src: sqlite3.Connection, dst: sqlite3.Connection, table: str):
    src.row_factory = sqlite3.Row
    rows = src.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        return
    cols = rows[0].keys()
    placeholders = ",".join("?" * len(cols))
    col_list = ",".join(cols)
    dst.executemany(
        f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})",
        [tuple(r) for r in rows],
    )
    dst.commit()
    src.row_factory = None


def get_demo_schema(src: sqlite3.Connection) -> str:
    rows = src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL ORDER BY rootpage"
    ).fetchall()
    return ";\n".join(r[0] for r in rows) + ";"


def main():
    if os.path.exists(DEMO_DB):
        os.remove(DEMO_DB)
        print(f"Removed existing {DEMO_DB}")

    src = connect(REAL_DB)
    dst = connect(DEMO_DB)

    # --- 1. Create schema in demo DB (same as real) ---
    schema_sql = get_demo_schema(src)
    for stmt in schema_sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                dst.execute(stmt)
            except Exception:
                pass
    dst.commit()
    print("Schema created.")

    # --- 2. Copy non-personal tables ---
    for table in ("instruments", "market_rates", "quotes", "instrument_code_mappings"):
        copy_table(src, dst, table)
        print(f"Copied {table}.")

    # --- 3. Load active instruments with their latest real prices ---
    src.row_factory = sqlite3.Row
    instruments = src.execute("""
        SELECT i.id, i.type, i.location, i.currency,
               mp.unit_price, mp.date as latest_date
        FROM instruments i
        LEFT JOIN monthly_positions mp ON mp.instrument_id = i.id
            AND mp.date = (SELECT MAX(date) FROM monthly_positions WHERE instrument_id = i.id)
        WHERE i.status = 'activo'
    """).fetchall()

    # USD rate from latest snapshot
    snap = src.execute(
        "SELECT usd_rate FROM portfolio_snapshots ORDER BY date DESC LIMIT 1"
    ).fetchone()
    usd_rate = snap["usd_rate"] if snap else 5.3

    # All distinct dates in real DB
    all_dates = [
        r[0] for r in src.execute(
            "SELECT DISTINCT date FROM monthly_positions ORDER BY date"
        ).fetchall()
    ]

    # --- 4. Assign a stable fake factor per instrument ---
    # For price-based: assign a fixed fake quantity
    # For balance-based: assign a fixed fake balance per instrument (consistent across time)
    inst_config = {}
    for inst in instruments:
        iid = inst["id"]
        itype = inst["type"]
        iloc = inst["location"]
        has_price = inst["unit_price"] is not None

        if has_price or (itype in ("accion", "fii") or iloc == "exterior"):
            qty_range = QTY_RANGES.get(itype, DEFAULT_QTY_RANGE)
            fake_qty = random.randint(*qty_range)
            inst_config[iid] = {"mode": "price", "qty": fake_qty}
        else:
            bal_range = BALANCE_RANGES.get(itype, DEFAULT_BALANCE_RANGE)
            # monthly growth: slight random drift per month
            base_balance = random.randint(*bal_range)
            inst_config[iid] = {"mode": "balance", "base": base_balance}

    # --- 5. Generate monthly_positions for all dates ---
    # For each instrument, only generate a position for dates where the real DB had one
    real_positions = src.execute("""
        SELECT instrument_id, date, unit_price, usd_rate, balance_usd
        FROM monthly_positions
        ORDER BY instrument_id, date
    """).fetchall()

    # Build set of (instrument_id, date) that exist in real DB
    real_pairs = {(r["instrument_id"], r["date"]) for r in real_positions}
    # Build map of real unit prices per (instrument_id, date)
    real_prices = {(r["instrument_id"], r["date"]): dict(r) for r in real_positions}

    demo_positions = []
    for inst in instruments:
        iid = inst["id"]
        cfg = inst_config.get(iid)
        if not cfg:
            continue

        # Only generate for dates where real DB had a position
        inst_dates = sorted(d for (i, d) in real_pairs if i == iid)
        if not inst_dates:
            continue

        for i, dt in enumerate(inst_dates):
            real_row = real_prices.get((iid, dt), {})
            up = real_row.get("unit_price") if real_row else None
            snap_usd_rate = real_row.get("usd_rate") if real_row else usd_rate

            if cfg["mode"] == "price" and up:
                qty = cfg["qty"]
                drift = 1.0 + random.uniform(-0.02, 0.02)
                balance_brl = round(qty * up * drift, 2)
                balance_usd = round(balance_brl / snap_usd_rate, 2) if snap_usd_rate and inst["currency"] == "USD" else None
                unit_price = round(up * drift, 4)
                quantity = qty
            elif cfg["mode"] == "price":
                # price-based instrument but no unit_price for this historical date — skip
                continue
            else:
                # Balance-based: slight monthly drift
                drift = 1.0 + random.uniform(-0.01, 0.015) * (i + 1) / len(inst_dates)
                balance_brl = round(cfg["base"] * drift, 2)
                balance_usd = round(balance_brl / snap_usd_rate, 2) if snap_usd_rate and inst["currency"] == "USD" else None
                unit_price = None
                quantity = None

            demo_positions.append((
                iid, dt,
                balance_brl, balance_usd,
                snap_usd_rate, unit_price, quantity,
            ))

    dst.executemany("""
        INSERT INTO monthly_positions
            (instrument_id, date, balance_brl, balance_usd, usd_rate, unit_price, quantity)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, demo_positions)
    dst.commit()
    print(f"Generated {len(demo_positions)} fake monthly_positions.")

    # --- 6. Build portfolio_snapshots from demo positions ---
    real_snaps = src.execute(
        "SELECT * FROM portfolio_snapshots ORDER BY date"
    ).fetchall()
    snap_cols = [d[0] for d in src.execute("SELECT * FROM portfolio_snapshots LIMIT 0").description]

    for snap_row in real_snaps:
        snap_dict = dict(zip(snap_cols, snap_row))
        snap_date = snap_dict["date"]
        snap_usd_rate = snap_dict.get("usd_rate") or usd_rate

        total_brl = dst.execute(
            "SELECT COALESCE(SUM(balance_brl), 0) FROM monthly_positions WHERE date = ?",
            (snap_date,)
        ).fetchone()[0]

        snap_dict["total_brl"] = round(total_brl, 2)
        snap_dict["total_with_prev"] = round(total_brl, 2)
        if snap_usd_rate:
            snap_dict["total_usd"] = round(total_brl / snap_usd_rate, 2)
            snap_dict["total_usd_with_prev"] = round(total_brl / snap_usd_rate, 2)

        # Zero out custodian breakdowns (personal data)
        for col in snap_cols:
            if col.endswith("_total") or col in ("hsbc_total", "bradesco_total", "xp_br_total",
                                                   "xp_us_total", "santander_total", "inter_total",
                                                   "brasil_total", "fgts", "prev", "usa_total"):
                snap_dict[col] = None

        cols = list(snap_dict.keys())
        vals = [snap_dict[c] for c in cols]
        dst.execute(
            f"INSERT OR REPLACE INTO portfolio_snapshots ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            vals
        )
    dst.commit()
    print(f"Generated {len(real_snaps)} portfolio_snapshots.")

    # --- 7. Scale provento_items proportionally ---
    prov_items = src.execute("SELECT * FROM provento_items").fetchall()
    pi_cols = [d[0] for d in src.execute("SELECT * FROM provento_items LIMIT 0").description]
    latest_date_val = all_dates[-1] if all_dates else None
    if latest_date_val:
        real_total = src.execute(
            "SELECT COALESCE(SUM(balance_brl), 0) FROM monthly_positions WHERE date = ?",
            (latest_date_val,)
        ).fetchone()[0]
        demo_total_val = dst.execute(
            "SELECT COALESCE(SUM(balance_brl), 0) FROM monthly_positions WHERE date = ?",
            (latest_date_val,)
        ).fetchone()[0]
        scale_pi = (demo_total_val / real_total) if real_total else 1.0
    else:
        scale_pi = 1.0

    for pirow in prov_items:
        pd = dict(zip(pi_cols, pirow))
        pd["amount_brl"] = round((pd["amount_brl"] or 0) * scale_pi, 2)
        cols = list(pd.keys())
        dst.execute(
            f"INSERT OR REPLACE INTO provento_items ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [pd[c] for c in cols]
        )
    dst.commit()
    print(f"Scaled {len(prov_items)} provento_items (factor={scale_pi:.3f}).")

    # Copy provento_forecast and provento_import_batches as-is
    for table in ("provento_forecast", "provento_import_batches"):
        try:
            copy_table(src, dst, table)
            print(f"Copied {table}.")
        except Exception as e:
            print(f"Skipped {table}: {e}")

    # --- 9. Scale proventos (old aggregate table) proportionally ---
    proventos = src.execute("SELECT * FROM proventos").fetchall()
    prov_cols = [d[0] for d in src.execute("SELECT * FROM proventos LIMIT 0").description]
    for prow in proventos:
        pd = dict(zip(prov_cols, prow))
        pd["amount"] = round((pd["amount"] or 0) * scale_pi, 2)
        cols = list(pd.keys())
        dst.execute(
            f"INSERT OR REPLACE INTO proventos ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [pd[c] for c in cols]
        )
    dst.commit()
    print(f"Scaled {len(proventos)} proventos (factor={scale_pi:.3f}).")

    # --- 10. Scale annual_summaries proportionally ---
    annual = src.execute("SELECT * FROM annual_summaries").fetchall()
    ann_cols = [d[0] for d in src.execute("SELECT * FROM annual_summaries LIMIT 0").description]
    for arow in annual:
        ad = dict(zip(ann_cols, arow))
        for col in ("total", "diff", "gain", "net_flow"):
            if ad.get(col) is not None:
                ad[col] = round(ad[col] * scale_pi, 2)
        cols = list(ad.keys())
        dst.execute(
            f"INSERT OR REPLACE INTO annual_summaries ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [ad[c] for c in cols]
        )
    dst.commit()
    print(f"Scaled {len(annual)} annual_summaries.")

    src.close()
    dst.close()

    print(f"\nDemo DB created at: {DEMO_DB}")
    print("Run verification:")
    print(f"  sqlite3 {DEMO_DB} \"SELECT COUNT(*) FROM monthly_positions;\"")
    print(f"  sqlite3 {DEMO_DB} \"SELECT SUM(balance_brl) FROM monthly_positions WHERE date='{latest_date_val}';\"")


if __name__ == "__main__":
    main()
