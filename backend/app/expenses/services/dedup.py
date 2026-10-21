"""Hash de deduplicación (ver revisión §3.4 / D-06).

- Con external_id (comprobante / ID de operación): clave natural, sin ordinal.
- Sin él: campos de la fila + ordinal de aparición entre filas idénticas del mismo archivo.
Importes en centavos enteros.
"""
import hashlib
import re
from collections import Counter
from decimal import Decimal


def cents(amount) -> int:
    return int((Decimal(str(amount)) * 100).to_integral_value())


def _norm_desc(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().upper())


def _h(parts) -> str:
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode()).hexdigest()


def assign_hashes(account_id: int, statement_period, rows) -> list[str]:
    """rows: objetos con los atributos de ParsedRow, en orden canónico. Devuelve un hash por fila."""
    seen: Counter = Counter()
    out = []
    for r in rows:
        if r.external_id:
            out.append(_h(["ext", account_id, r.external_id, r.currency, cents(r.amount)]))
            continue
        base = [
            account_id, r.date, r.purchase_date, cents(r.amount), r.currency, _norm_desc(r.description_raw),
            r.time, r.installment_number, r.installment_total, statement_period,
        ]
        key = _h(base)
        out.append(_h(base + [seen[key]]))
        seen[key] += 1
    return out
