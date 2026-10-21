"""Flujo de importación: detectar -> parsear -> dedup -> FX -> clasificar -> preview -> confirmar."""
import hashlib
import os
import tempfile
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.expenses.models import ExpAccount, ExpImportBatch, ExpLink, ExpTransaction
from app.expenses.models.fx_rate import PAIR_USDARS, PAIR_USDBRL
from app.expenses.parsers import NeedsDueDate, detect_parser
from app.expenses.parsers.base import ParseError
from app.expenses.services import fx, linking
from app.expenses.services.classifier import Classifier
from app.expenses.services.dedup import assign_hashes


class ImportError_(Exception):
    def __init__(self, status: int, detail):
        self.status, self.detail = status, detail


def suggest_accounts(db: Session, parser_key: str) -> list[ExpAccount]:
    return db.query(ExpAccount).filter_by(parser_key=parser_key, active=True).all()


def _json_safe(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def create_preview(db: Session, data: bytes, filename: str, account_id: Optional[int] = None,
                   due_date: Optional[date] = None, fetch=None) -> dict:
    # los PDF se detectan por contenido (necesitan el archivo completo); los CSV, por su cabecera
    parser = detect_parser(filename, data if data[:5] == b"%PDF-" else data[:4096])
    if parser is None:
        raise ImportError_(422, "Formato no reconocido")

    candidates = suggest_accounts(db, parser.key)
    if account_id is None:
        if len(candidates) != 1:
            raise ImportError_(422, {"message": "Elegí la cuenta", "candidates": [
                {"id": a.id, "name": a.name} for a in candidates]})
        account_id = candidates[0].id
    account = db.get(ExpAccount, account_id)
    if account is None:
        raise ImportError_(404, "Cuenta inexistente")

    file_hash = hashlib.sha256(data).hexdigest()
    prior = db.query(ExpImportBatch).filter_by(account_id=account_id, file_hash=file_hash).first()
    if prior and prior.status == "confirmed":
        raise ImportError_(409, "Este archivo ya fue importado para esta cuenta")
    if prior:  # preview o descartado previo: se reemplaza
        db.delete(prior); db.flush()

    # El parser lee desde disco; el nombre original no se persiste (puede contener nº de cuenta).
    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(filename)[1])
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        try:
            stmt = parser.parse(tmp, due_date=due_date) if due_date else _parse_with_name(parser, tmp, filename)
        except NeedsDueDate:
            raise ImportError_(422, {"message": "Falta la fecha de vencimiento", "needs_due_date": True})
        except ParseError as e:
            raise ImportError_(422, str(e))
    finally:
        os.unlink(tmp)

    hashes = assign_hashes(account_id, stmt.statement_period, stmt.rows)
    existing = {h for (h,) in db.query(ExpTransaction.dedup_hash).filter(ExpTransaction.dedup_hash.in_(hashes))} if hashes else set()

    if stmt.rows:
        lo, hi = min(r.date for r in stmt.rows), max(r.date for r in stmt.rows)
        pairs = [PAIR_USDBRL] + ([PAIR_USDARS] if any(r.currency == "ARS" for r in stmt.rows) else [])
        fx.refresh(db, lo, hi, fetch, pairs)

    clf = Classifier(db)
    rows = []
    for r, h in zip(stmt.rows, hashes):
        c = clf.classify(account_id, r.description_raw, r.counterparty, r.amount, r.kind_hint)
        conv = fx.convert(db, float(r.amount), r.currency, r.date, fetch)
        rows.append({
            **{k: _json_safe(v) for k, v in asdict(r).items()},
            "dedup_hash": h, "duplicate": h in existing,
            "kind": c.kind, "category_id": c.category_id, "entity_id": c.entity_id,
            "merchant_normalized": c.merchant_normalized, "classification_source": c.classification_source,
            "rule_id": c.rule_id, "needs_review": c.needs_review,
            "amount_brl": conv.amount_brl, "amount_usd": conv.amount_usd, "fx_usd_brl": conv.fx_usd_brl,
            "fx_ars_usd": conv.fx_ars_usd, "fx_estimated": conv.estimated,
        })

    batch = ExpImportBatch(
        account_id=account_id, file_label=f"{stmt.parser_key}:{file_hash[:8]}", file_hash=file_hash,
        parser_key=stmt.parser_key, period_start=stmt.period_start, period_end=stmt.period_end,
        statement_due_date=stmt.statement_due_date, statement_period=stmt.statement_period,
        statement_totals={k: _json_safe(v) for k, v in stmt.declared_totals.items()},
        validation=[asdict(c) for c in stmt.validation], preview_rows=rows,
        rows_total=len(rows), rows_new=sum(1 for x in rows if not x["duplicate"]),
        rows_duplicate=sum(1 for x in rows if x["duplicate"]), status="preview",
    )
    db.add(batch); db.commit()
    return batch_detail(batch, with_rows=True)


def _parse_with_name(parser, tmp_path: str, filename: str):
    """Algunos parsers infieren datos del nombre (vencimiento de las faturas)."""
    from datetime import date as _d
    import re
    m = re.search(r"Fatura(\d{4})-(\d{2})-(\d{2})", filename, re.I)
    if parser.key == "xp_card_csv" and m:
        return parser.parse(tmp_path, due_date=_d(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return parser.parse(tmp_path)


def batch_detail(b: ExpImportBatch, with_rows: bool = False) -> dict:
    out = {
        "id": b.id, "account_id": b.account_id, "parser_key": b.parser_key, "status": b.status,
        "period_start": _json_safe(b.period_start), "period_end": _json_safe(b.period_end),
        "statement_due_date": _json_safe(b.statement_due_date), "statement_period": b.statement_period,
        "statement_totals": b.statement_totals, "validation": b.validation,
        "rows_total": b.rows_total, "rows_new": b.rows_new, "rows_duplicate": b.rows_duplicate,
        "created_at": _json_safe(b.created_at), "confirmed_at": _json_safe(b.confirmed_at),
    }
    if with_rows:
        out["rows"] = b.preview_rows or []
    return out


def confirm(db: Session, batch_id: int, overrides: Optional[list[dict]] = None, force: bool = False,
            account_id: Optional[int] = None) -> dict:
    b = db.get(ExpImportBatch, batch_id)
    if b is None:
        raise ImportError_(404, "Lote inexistente")
    if b.status != "preview":
        raise ImportError_(409, f"El lote está {b.status}")
    failed = [c for c in (b.validation or []) if not c["ok"]]
    if failed and not force:
        raise ImportError_(422, {"message": "Fallan checks de validación", "checks": failed})
    if account_id is not None and account_id != b.account_id:
        raise ImportError_(422, "Cambiar de cuenta requiere un nuevo preview")

    ov = {o["index"]: o for o in (overrides or [])}
    inserted = duplicated = 0
    for i, row in enumerate(b.preview_rows or []):
        if row["duplicate"]:
            duplicated += 1
            continue
        o = ov.get(i, {})
        manual = any(k in o for k in ("kind", "category_id", "entity_id"))
        tx = ExpTransaction(
            account_id=b.account_id, batch_id=b.id, date=date.fromisoformat(row["date"]),
            purchase_date=date.fromisoformat(row["purchase_date"]) if row.get("purchase_date") else None,
            statement_period=b.statement_period, description_raw=row["description_raw"],
            counterparty=row.get("counterparty"), merchant_normalized=row.get("merchant_normalized"),
            external_id=row.get("external_id"), amount=row["amount"], currency=row["currency"],
            fx_usd_brl=row.get("fx_usd_brl"), fx_ars_usd=row.get("fx_ars_usd"),
            fx_estimated=row.get("fx_estimated", False), amount_brl=row.get("amount_brl"),
            amount_usd=row.get("amount_usd"), kind=o.get("kind", row["kind"]),
            category_id=o.get("category_id", row["category_id"]), entity_id=o.get("entity_id", row["entity_id"]),
            installment_number=row.get("installment_number"), installment_total=row.get("installment_total"),
            classification_source="manual" if manual else row["classification_source"],
            rule_id=None if manual else row["rule_id"],
            needs_review=False if manual else row["needs_review"], dedup_hash=row["dedup_hash"],
        )
        try:
            with db.begin_nested():
                db.add(tx)
        except IntegrityError:  # carrera con otro import: ya existe
            duplicated += 1
            continue
        inserted += 1
    b.status, b.confirmed_at = "confirmed", datetime.utcnow()
    b.rows_new, b.rows_duplicate = inserted, duplicated
    b.preview_rows = None
    db.commit()
    linking.rebuild(db)
    return batch_detail(b)


def delete_batch(db: Session, batch_id: int) -> dict:
    b = db.get(ExpImportBatch, batch_id)
    if b is None:
        raise ImportError_(404, "Lote inexistente")
    if b.status != "confirmed":
        db.delete(b); db.commit()
        return {"deleted_rows": 0}
    ids = [i for (i,) in db.query(ExpTransaction.id).filter_by(batch_id=b.id)]
    if ids:
        db.query(ExpLink).filter(ExpLink.exp_transaction_id.in_(ids)).delete(synchronize_session=False)
        # liberar pares de transferencias cuyo compañero se borra
        groups = {g for (g,) in db.query(ExpTransaction.transfer_group_id).filter(
            ExpTransaction.id.in_(ids), ExpTransaction.transfer_group_id.isnot(None))}
        if groups:
            db.query(ExpTransaction).filter(
                ExpTransaction.transfer_group_id.in_(groups), ExpTransaction.batch_id != b.id
            ).update({"transfer_group_id": None}, synchronize_session=False)
    db.query(ExpTransaction).filter(ExpTransaction.statement_batch_id == b.id).update(
        {"statement_batch_id": None}, synchronize_session=False)
    n = db.query(ExpTransaction).filter_by(batch_id=b.id).delete(synchronize_session=False)
    db.delete(b); db.commit()
    linking.rebuild(db)
    return {"deleted_rows": n}
