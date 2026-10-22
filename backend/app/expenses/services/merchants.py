"""Pendientes agrupados por comercio: clasificar un comercio una vez crea una regla y la aplica a todas sus filas."""
import re
from collections import Counter, defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from app.expenses.models import ExpAccount, ExpRule, ExpTransaction
from app.expenses.services.review import INTERNAL_MARKERS
from app.expenses.models.transaction import KINDS
from app.expenses.services import linking, rules as rules_svc
from app.expenses.services.normalize import match_key


def pending_groups(db: Session, limit: int = 200) -> list[dict]:
    """Filas sin clasificar (default, no manuales) agrupadas por comercio normalizado y signo."""
    countries = {a.id: a.country for a in db.query(ExpAccount)}
    groups: dict[tuple[str, bool], list[ExpTransaction]] = defaultdict(list)
    q = db.query(ExpTransaction).filter(
        ExpTransaction.needs_review.is_(True), ExpTransaction.classification_source == "default")
    for t in q:
        key = match_key(t.merchant_normalized or t.description_raw)
        if key:
            groups[(key, t.amount > 0)].append(t)
    out = []
    for (key, positive), txs in groups.items():
        display = Counter(t.merchant_normalized or t.description_raw for t in txs).most_common(1)[0][0]
        out.append({
            "key": key, "sign": "positive" if positive else "negative", "merchant": display[:80], "count": len(txs),
            "total_brl": round(sum(abs(t.amount_brl or 0) for t in txs), 2),
            "first": min(t.date for t in txs).isoformat(), "last": max(t.date for t in txs).isoformat(),
            "countries": sorted({countries[t.account_id] for t in txs}),
            "sample": [t.description_raw[:90] for t in txs[:2]],
        })
    out.sort(key=lambda g: (-g["total_brl"], -g["count"]))
    return out[:limit]


def apply_groups(db: Session, items: list[dict]) -> list[dict]:
    """items: {key, sign, kind, category_id?, entity_id?, needs_review?}. Crea (o actualiza) una regla anclada
    por comercio y la aplica a las filas pendientes. Nunca pisa clasificaciones manuales."""
    results = []
    for it in items:
        if it["kind"] not in KINDS:
            raise ValueError(f"kind inválido: {it['kind']}")
        key = re.sub(r"[^A-Z0-9]", "", it["key"].upper())
        if not key:
            raise ValueError("clave de comercio vacía")
        pattern, sign = f"^{key}$", it.get("sign", "any")
        rule: Optional[ExpRule] = db.query(ExpRule).filter_by(
            pattern=pattern, field="merchant_normalized", amount_sign=sign, origin="manual").first()
        if rule is None:
            rule = ExpRule(pattern=pattern, field="merchant_normalized", amount_sign=sign, origin="manual", priority=50)
            db.add(rule)
        rule.set_kind, rule.set_category_id, rule.set_entity_id = it["kind"], it.get("category_id"), it.get("entity_id")
        rule.set_needs_review = bool(it.get("needs_review", False))
        db.commit()
        results.append({"key": key, "rule_id": rule.id, "applied": rules_svc.apply_rule_to_pending(db, rule)})
    return results


def unpaired_groups(db: Session, limit: int = 200) -> list[dict]:
    """Transferencias propias sin par y sin cuenta de contraparte declarada, agrupadas por descripción."""
    groups: dict[tuple[str, bool], list[ExpTransaction]] = defaultdict(list)
    for t in db.query(ExpTransaction).filter(
            ExpTransaction.kind == "own_transfer", ExpTransaction.transfer_group_id.is_(None),
            ExpTransaction.counterparty_account_id.is_(None)):
        if any(m in t.description_raw.lower() for m in INTERNAL_MARKERS):
            continue
        key = match_key(t.merchant_normalized or t.description_raw)
        if key:
            groups[(key, t.amount > 0)].append(t)
    out = [{
        "key": key, "sign": "positive" if pos else "negative", "count": len(txs),
        "merchant": Counter(t.merchant_normalized or t.description_raw for t in txs).most_common(1)[0][0][:80],
        "total_brl": round(sum(abs(t.amount_brl or 0) for t in txs), 2),
        "first": min(t.date for t in txs).isoformat(), "last": max(t.date for t in txs).isoformat(),
        "accounts": sorted({t.account_id for t in txs}), "sample": [t.description_raw[:90] for t in txs[:2]],
    } for (key, pos), txs in groups.items()]
    out.sort(key=lambda g: (-g["total_brl"], -g["count"]))
    return out[:limit]


def apply_counterparty(db: Session, items: list[dict]) -> list[dict]:
    """items: {key, sign, account_id}. Fija la cuenta de contraparte en todas las transferencias propias
    sin par de ese grupo y guarda una regla para los próximos imports. Luego reintenta el pareo."""
    accounts = {a.id for a in db.query(ExpAccount)}
    results = []
    for it in items:
        if it["account_id"] not in accounts:
            raise ValueError("cuenta inexistente")
        key = re.sub(r"[^A-Z0-9]", "", it["key"].upper())
        if not key:
            raise ValueError("clave vacía")
        sign = it.get("sign", "any")
        pattern = f"^{key}$"
        rule = db.query(ExpRule).filter_by(pattern=pattern, field="merchant_normalized", amount_sign=sign, origin="manual").first()
        if rule is None:
            rule = ExpRule(pattern=pattern, field="merchant_normalized", amount_sign=sign, origin="manual", priority=50)
            db.add(rule)
        rule.set_kind, rule.set_counterparty_account_id = "own_transfer", it["account_id"]
        n = 0
        for t in db.query(ExpTransaction).filter(
                ExpTransaction.kind == "own_transfer", ExpTransaction.counterparty_account_id.is_(None)):
            positive = t.amount > 0
            if (sign == "positive") != positive and sign != "any":
                continue
            if match_key(t.merchant_normalized or t.description_raw) == key and t.account_id != it["account_id"]:
                t.counterparty_account_id = it["account_id"]; n += 1
        db.commit()
        results.append({"key": key, "rule_id": rule.id, "assigned": n})
    linking.rebuild(db)
    return results
