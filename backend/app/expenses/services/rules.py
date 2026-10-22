import json
import os
import pathlib
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.expenses.models import ExpCategory, ExpEntity, ExpRule, ExpTransaction
from app.expenses.services.classifier import Classifier, sign_inconsistent
from app.expenses.services.normalize import match_key

SEED_DIR = pathlib.Path(__file__).resolve().parent.parent / "seed"
EXAMPLE_RULES = SEED_DIR / "rules.example.json"   # sin nombres reales: es lo único que ve el entorno demo


def load_seed_rules(db: Session, path: Optional[pathlib.Path] = None) -> int:
    """Carga idempotente por seed_key. Usa rules.local.json si existe, si no rules.example.json.
    Una regla seed ya existente se actualiza sólo si sigue con origin='seed'."""
    env = os.getenv("EXPENSES_RULES_FILE")
    path = path or (pathlib.Path(env) if env else None) or next(
        (p for p in (SEED_DIR / "rules.local.json", SEED_DIR / "rules.example.json") if p.exists()), None)
    if path is None:
        return 0
    cats = {c.name: c.id for c in db.query(ExpCategory)}
    ents = {e.code: e.id for e in db.query(ExpEntity)}
    n = 0
    for item in json.loads(path.read_text(encoding="utf-8")):
        key = item["seed_key"]
        values = dict(
            priority=item.get("priority", 100), field=item.get("field", "description_raw"),
            pattern=item["pattern"], amount_sign=item.get("amount_sign", "any"), set_kind=item["kind"],
            set_category_id=cats[item["category"]] if item.get("category") else None,
            set_entity_id=ents[item["entity"]] if item.get("entity") else None,
            set_merchant=item.get("merchant"), set_needs_review=bool(item.get("needs_review", False)),
            set_exclude_from_audit=bool(item.get("exclude_from_audit", False)),
            origin="seed",
        )
        rule = db.query(ExpRule).filter_by(seed_key=key).first()
        if rule is None:
            db.add(ExpRule(seed_key=key, **values)); n += 1
        elif rule.origin == "seed":
            for k, v in values.items():
                setattr(rule, k, v)
    db.commit()
    return n


def matches_pending(rule: ExpRule, tx: ExpTransaction) -> bool:
    if rule.account_id not in (None, tx.account_id):
        return False
    if (rule.amount_sign == "positive" and tx.amount <= 0) or (rule.amount_sign == "negative" and tx.amount >= 0):
        return False
    hay = {
        "description_raw": tx.description_raw, "counterparty": tx.counterparty or "",
        "merchant_normalized": match_key(tx.merchant_normalized or tx.description_raw),
    }[rule.field]
    return bool(re.search(rule.pattern, hay, re.I))


def pending_matches(db: Session, rule: ExpRule) -> list[ExpTransaction]:
    """Filas que la regla reclasificaría: sólo needs_review y nunca las manuales."""
    q = db.query(ExpTransaction).filter(
        ExpTransaction.needs_review.is_(True), ExpTransaction.classification_source != "manual")
    return [t for t in q if matches_pending(rule, t)]


def apply_rule_to_pending(db: Session, rule: ExpRule) -> int:
    from app.expenses.services.classifier import _sign_adjust
    txs = pending_matches(db, rule)
    for t in txs:
        t.kind = _sign_adjust(rule.set_kind, t.amount)
        if rule.set_category_id:
            t.category_id = rule.set_category_id
        if rule.set_entity_id:
            t.entity_id = rule.set_entity_id
        t.classification_source = "rule"
        t.rule_id = rule.id
        t.needs_review = sign_inconsistent(t.kind, t.amount) or bool(rule.set_needs_review)
        if rule.set_counterparty_account_id:
            t.counterparty_account_id = rule.set_counterparty_account_id
        if rule.set_exclude_from_audit:
            t.exclude_from_audit = True
    db.commit()
    return len(txs)


def reclassify_pending(db: Session, include_rule_rows: bool = False) -> dict:
    """Vuelve a pasar por las reglas vigentes las filas pendientes (nunca las manuales). Sólo cambia las que
    ahora matchean alguna regla o identificador propio; el resto queda como estaba.

    include_rule_rows=True re-evalúa también las filas ya clasificadas por una regla (no las manuales ni las
    de cuenta propia): sirve cuando una regla cambió o se agregó una que debe afectar a filas existentes."""
    from app.expenses.services.classifier import Classifier
    clf = Classifier(db)
    changed = resolved = 0
    q = db.query(ExpTransaction).filter(ExpTransaction.classification_source != "manual")
    if include_rule_rows:
        q = q.filter((ExpTransaction.needs_review.is_(True)) | (ExpTransaction.classification_source == "rule"))
    else:
        q = q.filter(ExpTransaction.needs_review.is_(True))
    for t in q:
        c = clf.classify(t.account_id, t.description_raw, t.counterparty, t.amount)
        if c.classification_source == "default":
            continue
        before = (t.kind, t.category_id, t.entity_id, t.rule_id, t.needs_review, t.counterparty_account_id, t.exclude_from_audit)
        t.kind, t.category_id, t.entity_id = c.kind, c.category_id, c.entity_id
        t.merchant_normalized, t.classification_source, t.rule_id = c.merchant_normalized, c.classification_source, c.rule_id
        t.needs_review = c.needs_review
        if c.counterparty_account_id:
            t.counterparty_account_id = c.counterparty_account_id
        if c.exclude_from_audit:
            t.exclude_from_audit = True
        if before != (t.kind, t.category_id, t.entity_id, t.rule_id, t.needs_review, t.counterparty_account_id, t.exclude_from_audit):
            changed += 1
            resolved += 0 if c.needs_review else 1
    db.commit()
    return {"reclassified": changed, "resolved": resolved}
