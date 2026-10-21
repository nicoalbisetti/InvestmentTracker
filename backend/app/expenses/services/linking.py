"""Conciliación interna: pares de transferencias, pagos de fatura y cobertura de tarjetas.

Los vínculos internos viven en columnas de exp_transactions (transfer_group_id, statement_batch_id).
La conciliación con inversiones/proventos (lectura de tablas de inversiones) se agrega en este mismo
módulo en una etapa posterior: es el único lugar donde se permite importar código de inversiones.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations
from typing import Optional

from sqlalchemy.orm import Session

# Único módulo de gastos autorizado a leer las tablas de inversiones (ver tests/test_architecture).
from app.database import get_db as get_inv_db  # noqa: F401  (dependencia de sesión de inversiones)
from app.models import (  # noqa: F401  (registra todos los mappers: Instrument tiene relaciones con varios modelos)
    annual_summary, equity_trade, import_log, instrument_code_mapping, market_rate, monthly_position,
    portfolio_snapshot, provento, provento_forecast, quote)
from app.models.instrument import Instrument
from app.models.provento_item import ProvéntoItem
from app.models.transaction import Transaction

from app.expenses.models import ExpAccount, ExpImportBatch, ExpLink, ExpTransaction
from app.expenses.services.dedup import cents

PAIR_KINDS = {"own_transfer": 2, "card_payment": 45}  # kind -> ventana en días
CONFIRM_DAYS = {"own_transfer": 1}                    # Δ máximo para confirmar sin revisión
STATEMENT_EXACT_WINDOW = (-5, 45)                     # pago - vencimiento, con monto exacto
STATEMENT_COVER_WINDOW = (-5, 25)                     # cobertura sin monto exacto (pagos parciales)


@dataclass
class Edge:
    a: ExpTransaction  # salida (negativo)
    b: ExpTransaction  # entrada (positivo)
    delta: int


def _edges(txs: list[ExpTransaction], kind: str) -> list[Edge]:
    window = PAIR_KINDS[kind]
    outs = [t for t in txs if t.amount < 0]
    ins = defaultdict(list)
    for t in txs:
        if t.amount > 0:
            ins[(cents(t.amount), t.currency)].append(t)
    edges = []
    for a in outs:
        for b in ins.get((cents(-a.amount), a.currency), []):
            d = abs((b.date - a.date).days)
            if b.account_id != a.account_id and d <= window:
                edges.append(Edge(a, b, d))
    return edges


def _split(edges: list[Edge], kind: str):
    """(confirmables, sugeridas). Confirmable: sin ambigüedad (grado 1 o estrictamente más cercano)."""
    by_a, by_b = defaultdict(list), defaultdict(list)
    for e in edges:
        by_a[e.a.id].append(e); by_b[e.b.id].append(e)

    def best(es, e):
        return all(e.delta < o.delta for o in es if o is not e)

    confirm, rest = [], []
    for e in sorted(edges, key=lambda x: x.delta):
        limit = CONFIRM_DAYS.get(kind)
        ok_delta = limit is None or e.delta <= limit
        if ok_delta and best(by_a[e.a.id], e) and best(by_b[e.b.id], e):
            confirm.append(e)
        else:
            rest.append(e)
    return confirm, rest


def _unlinked(db: Session, kind: str) -> list[ExpTransaction]:
    return db.query(ExpTransaction).filter(
        ExpTransaction.kind == kind, ExpTransaction.transfer_group_id.is_(None)).all()


def link_pairs(db: Session) -> int:
    """Asigna transfer_group_id (= menor id del par) a los pares inequívocos. Idempotente."""
    n = 0
    for kind in PAIR_KINDS:
        used: set[int] = set()
        while True:  # tras confirmar, los nodos libres pueden quedar sin ambigüedad
            edges = [e for e in _edges(_unlinked(db, kind), kind) if e.a.id not in used and e.b.id not in used]
            confirm, _ = _split(edges, kind)
            if not confirm:
                break
            for e in confirm:
                if e.a.id in used or e.b.id in used:
                    continue
                gid = min(e.a.id, e.b.id)
                e.a.transfer_group_id = e.b.transfer_group_id = gid
                used.update((e.a.id, e.b.id)); n += 1
            db.flush()
    db.commit()
    return n


ADOPTABLE_KINDS = ("income", "expense", "refund", "unknown")


def adopt_counterparts(db: Session) -> int:
    """Una transferencia propia sin par adopta a su contraparte exacta aunque ésta no se haya
    reconocido como propia (p. ej. el banco receptor muestra otro nombre para la billetera de origen).

    Sólo si: otra cuenta, importe y moneda idénticos, signo opuesto, a lo sumo 1 día de diferencia,
    candidato único para ambos lados y la contraparte no fue clasificada a mano.
    """
    lonely = _unlinked(db, "own_transfer")
    candidates = db.query(ExpTransaction).filter(
        ExpTransaction.kind.in_(ADOPTABLE_KINDS), ExpTransaction.classification_source != "manual").all()
    by_key = defaultdict(list)
    for c in candidates:
        by_key[(cents(abs(c.amount)), c.currency, c.amount > 0)].append(c)
    cand_for: dict[int, list[ExpTransaction]] = {}
    for t in lonely:
        cand_for[t.id] = [c for c in by_key.get((cents(abs(t.amount)), t.currency, t.amount < 0), [])
                          if c.account_id != t.account_id and abs((c.date - t.date).days) <= 1]
    claims = defaultdict(list)
    for t in lonely:
        for c in cand_for[t.id]:
            claims[c.id].append(t)
    n = 0
    for t in lonely:
        cs = cand_for[t.id]
        if len(cs) == 1 and len(claims[cs[0].id]) == 1:
            c = cs[0]
            c.kind, c.classification_source, c.rule_id, c.needs_review = "own_transfer", "own_account", None, False
            t.transfer_group_id = c.transfer_group_id = min(t.id, c.id)
            n += 1
    db.commit()
    return n


def pair_suggestions(db: Session) -> list[dict]:
    """Candidatos ambiguos o de Δ mayor al de auto-confirmación (no se persisten)."""
    out = []
    for kind in PAIR_KINDS:
        _, rest = _split(_edges(_unlinked(db, kind), kind), kind)
        out += [{"kind": kind, "out_id": e.a.id, "in_id": e.b.id, "amount": e.b.amount,
                 "days": e.delta} for e in rest]
    return out


def payer_card_payments(db: Session) -> list[ExpTransaction]:
    """Pagos de tarjeta del lado de la cuenta pagadora (no de la cuenta de la tarjeta)."""
    return (db.query(ExpTransaction).join(ExpAccount, ExpAccount.id == ExpTransaction.account_id)
            .filter(ExpTransaction.kind == "card_payment", ExpAccount.kind != "credit_card").all())


def _statement_total(b: ExpImportBatch, currency: str) -> Optional[float]:
    t = (b.statement_totals or {})
    v = t.get("statement_total") if currency == "BRL" else t.get(currency)
    return round(v, 2) if v is not None else None


BRAND_WORDS = {"visa": "visa", "amex": "amex", "american express": "amex", "mastercard": "mastercard",
               "master card": "mastercard", "naranja": "naranja", "cabal": "cabal"}


def _brands(text: str) -> set[str]:
    """Marcas de tarjeta mencionadas. Si el pago nombra una marca, sólo puede cubrirlo una fatura de esa marca."""
    low = text.lower()
    return {v for k, v in BRAND_WORDS.items() if k in low}


def link_statements(db: Session) -> int:
    """Vincula pagos de la cuenta pagadora a su fatura (statement_batch_id).

    Cobertura: un pago dentro de la ventana de vencimiento de una fatura importada de la tarjeta que se
    paga desde esa cuenta queda cubierto aunque el monto no coincida (pagos parciales, cargos, TC).
    Un pago sin fatura cercana sigue sin vínculo: se contará como 'Tarjeta sin detalle'.
    """
    cards = defaultdict(list)  # cuenta pagadora -> tarjetas
    for a in db.query(ExpAccount).filter(ExpAccount.paid_from_account_id.isnot(None)):
        cards[a.paid_from_account_id].append(a.id)
    batches = defaultdict(list)
    for b in db.query(ExpImportBatch).filter_by(status="confirmed").filter(ExpImportBatch.statement_due_date.isnot(None)):
        batches[b.account_id].append(b)

    accounts = {a.id: a for a in db.query(ExpAccount)}
    n = 0
    for tx in payer_card_payments(db):
        brands = _brands(tx.description_raw)
        cands = [b for cid in cards.get(tx.account_id, []) for b in batches.get(cid, [])
                 if not brands or brands & _brands(f"{accounts[cid].name} {accounts[cid].institution}")]
        best, best_exact = None, False
        for b in cands:
            diff = (tx.date - b.statement_due_date).days
            exact = _statement_total(b, tx.currency) == round(-tx.amount, 2)
            lo, hi = STATEMENT_EXACT_WINDOW if exact else STATEMENT_COVER_WINDOW
            if not lo <= diff <= hi:
                continue
            key = (not exact, abs(diff))
            if best is None or key < (not best_exact, abs((tx.date - best.statement_due_date).days)):
                best, best_exact = b, exact
        new = best.id if best else None
        if tx.statement_batch_id != new:
            tx.statement_batch_id = new; n += 1
    db.commit()
    return n


def rebuild(db: Session) -> dict:
    pairs = link_pairs(db)
    adopted = adopt_counterparts(db)
    return {"pairs": pairs, "adopted": adopted, "statements": link_statements(db)}


def is_exact_statement_link(db: Session, tx: ExpTransaction) -> bool:
    """Exacto si el monto iguala el total de la fatura, o si el pago está emparejado con el crédito
    del mismo importe que aparece en la fatura siguiente (tarjetas AR: débito = pesos + USD x TC)."""
    b = db.get(ExpImportBatch, tx.statement_batch_id) if tx.statement_batch_id else None
    if b is None:
        return False
    return _statement_total(b, tx.currency) == round(-tx.amount, 2) or tx.transfer_group_id is not None


def unlink_pair(db: Session, tx: ExpTransaction) -> None:
    if tx.transfer_group_id is not None:
        db.query(ExpTransaction).filter_by(transfer_group_id=tx.transfer_group_id).update(
            {"transfer_group_id": None}, synchronize_session=False)


# ===================================================================================================
# Inversiones y proventos (lectura de las tablas de inversiones; escritura sólo en exp_links)
# ===================================================================================================
INV_WINDOW_DAYS = 30
INV_TOL = 0.005          # monto exacto (0,5 %)
FGC_TOL = 0.06           # el FGC paga distinto al último saldo (hasta 6 %)
PROV_WINDOW_DAYS = 35
PROV_TOL = 0.015
MAX_POOL, MAX_K = 12, 3
ACTIVE = ("suggested", "confirmed")


def _is_fgc(tx: ExpTransaction) -> bool:
    return "fundo garantidor" in tx.description_raw.lower()


def best_subset(items: list[tuple[int, float, int]], target: float, tol: float, max_k: int = MAX_K):
    """items: (id, monto, días_de_distancia). Subconjunto (≤ max_k) cuya suma se acerca más a `target`
    dentro de la tolerancia relativa. Devuelve (ids, diferencia_relativa) o None."""
    pool = sorted(items, key=lambda i: i[2])[:MAX_POOL]
    best = None
    for k in range(1, max_k + 1):
        for combo in combinations(pool, k):
            rel = abs(sum(c[1] for c in combo) - target) / target if target else 1
            if rel <= tol:
                key = (round(rel, 6), k, sum(c[2] for c in combo))
                if best is None or key < best[0]:
                    best = (key, combo, rel)
    return None if best is None else ([c[0] for c in best[1]], best[2])


def _score(rel: float, tol: float, days: int, window: int) -> float:
    return round(max(0.0, 1 - rel / tol) * 0.6 + max(0.0, 1 - days / window) * 0.4, 3)


def _linked_exp_ids(db: Session, link_type: str) -> set[int]:
    return {i for (i,) in db.query(ExpLink.exp_transaction_id).filter(
        ExpLink.link_type == link_type, ExpLink.status.in_(ACTIVE))}


def _used_targets(db: Session, target_type: str) -> set[int]:
    return {i for (i,) in db.query(ExpLink.target_id).filter(
        ExpLink.target_type == target_type, ExpLink.status.in_(ACTIVE))}


def _rejected_pairs(db: Session, target_type: str) -> set[tuple[int, int]]:
    return {(a, b) for a, b in db.query(ExpLink.exp_transaction_id, ExpLink.target_id).filter(
        ExpLink.target_type == target_type, ExpLink.status == "rejected")}


def link_investments(db: Session, inv: Session) -> int:
    """Sugiere (nunca confirma) vínculos aporte/rescate bancario <-> Transaction de inversiones.

    1 movimiento puede explicarse con hasta 3 transacciones (p. ej. 1 TED del FGC = 2 rescates).
    Una transferencia propia positiva sin par (el rescate llega por otra cuenta) también puede ser
    la contraparte bancaria de un rescate cuando el monto coincide exacto.
    """
    done = _linked_exp_ids(db, "investment")
    used = _used_targets(db, "investment_transaction")
    rejected = _rejected_pairs(db, "investment_transaction")
    txs = inv.query(Transaction).all()
    inst = {i.id: i for i in inv.query(Instrument)}
    created = 0
    sources = db.query(ExpTransaction).filter(
        ExpTransaction.kind.in_(("investment_contribution", "investment_withdrawal"))).order_by(ExpTransaction.date).all()
    sources += [t for t in db.query(ExpTransaction).filter(
        ExpTransaction.kind == "own_transfer", ExpTransaction.amount > 0, ExpTransaction.transfer_group_id.is_(None))]
    for e in sources:
        if e.id in done:
            continue
        withdrawal = e.amount > 0
        type_ = "rescate" if withdrawal else "aplicacion"
        fgc = _is_fgc(e)
        tol = FGC_TOL if fgc else INV_TOL
        window = 5 if e.kind == "own_transfer" else INV_WINDOW_DAYS
        target = abs(e.amount_brl if e.amount_brl is not None else e.amount)
        pool = []
        for t in txs:
            if t.type != type_ or t.id in used or (e.id, t.id) in rejected or t.amount_brl is None:
                continue
            days = abs((t.date - e.date).days)
            if days > window or (fgc and not (inst.get(t.instrument_id) and inst[t.instrument_id].in_liquidation)):
                continue
            pool.append((t.id, abs(t.amount_brl), days))
        found = best_subset(pool, target, tol if e.kind != "own_transfer" else 0.0005)
        if not found:
            continue
        ids, rel = found
        by_id = {t.id: t for t in txs}
        for tid in ids:
            t = by_id[tid]
            days = abs((t.date - e.date).days)
            db.add(ExpLink(
                exp_transaction_id=e.id, target_type="investment_transaction", target_id=tid, link_type="investment",
                amount_allocated_brl=abs(t.amount_brl), status="suggested", score=_score(rel, tol, days, window),
                target_date=t.date, target_amount=abs(t.amount_brl),
                target_label=getattr(inst.get(t.instrument_id), "name", None)))
            used.add(tid); created += 1
    db.commit()
    return created


def link_proventos(db: Session, inv: Session) -> int:
    """Cobro bancario (kind=provento) <-> ProvéntoItem. 1 cobro -> N proventos, y N cobros -> 1 provento
    (p. ej. un dividendo cobrado en dos cuentas). No filtra por custodia. Siempre sugerido."""
    done = _linked_exp_ids(db, "provento")
    used = _used_targets(db, "provento_item")
    rejected = _rejected_pairs(db, "provento_item")
    items = inv.query(ProvéntoItem).all()
    inst = {i.id: i for i in inv.query(Instrument)}
    by_id = {i.id: i for i in items}
    cobros = db.query(ExpTransaction).filter(ExpTransaction.kind == "provento", ExpTransaction.amount > 0) \
        .order_by(ExpTransaction.date).all()
    created = 0

    def add(e, item, allocated, rel, days):
        nonlocal created
        db.add(ExpLink(
            exp_transaction_id=e.id, target_type="provento_item", target_id=item.id, link_type="provento",
            amount_allocated_brl=allocated, status="suggested", score=_score(rel, PROV_TOL, days, PROV_WINDOW_DAYS),
            target_date=item.date, target_amount=item.amount_brl,
            target_label=getattr(inst.get(item.instrument_id), "name", None)))
        created += 1

    pending = []
    for e in cobros:
        if e.id in done:
            continue
        target = e.amount_brl if e.amount_brl is not None else e.amount
        pool = [(i.id, i.amount_brl, abs((i.date - e.date).days)) for i in items
                if i.id not in used and (e.id, i.id) not in rejected and abs((i.date - e.date).days) <= PROV_WINDOW_DAYS]
        found = best_subset(pool, target, PROV_TOL)
        if found:
            ids, rel = found
            for iid in ids:
                add(e, by_id[iid], by_id[iid].amount_brl, rel, abs((by_id[iid].date - e.date).days)); used.add(iid)
        else:
            pending.append(e)
    # N cobros -> 1 provento: combinaciones de cobros sin vincular cercanos entre sí
    for item in items:
        if item.id in used:
            continue
        near = [(e.id, e.amount_brl if e.amount_brl is not None else e.amount, abs((item.date - e.date).days))
                for e in pending if abs((item.date - e.date).days) <= PROV_WINDOW_DAYS and (e.id, item.id) not in rejected]
        found = best_subset(near, item.amount_brl, PROV_TOL, max_k=3)
        if found and len(found[0]) > 1:
            ids, rel = found
            for eid in ids:
                e = next(x for x in pending if x.id == eid)
                add(e, item, e.amount_brl if e.amount_brl is not None else e.amount, rel, abs((item.date - e.date).days))
            used.add(item.id)
            pending = [x for x in pending if x.id not in ids]
    db.commit()
    return created


def rebuild_investments(db: Session, inv: Session) -> dict:
    return {"investments": link_investments(db, inv), "proventos": link_proventos(db, inv)}


def set_link_status(db: Session, link_id: int, status: str) -> Optional[ExpLink]:
    link = db.get(ExpLink, link_id)
    if link is None:
        return None
    link.status = status
    if status == "confirmed":
        # al confirmar un vínculo se descartan las alternativas sugeridas para el mismo destino
        db.query(ExpLink).filter(
            ExpLink.target_type == link.target_type, ExpLink.target_id == link.target_id,
            ExpLink.id != link.id, ExpLink.status == "suggested").update({"status": "rejected"})
    db.commit()
    return link


def suggestions(db: Session, status: str = "suggested") -> list[dict]:
    """Vínculos agrupados por movimiento bancario, con la diferencia entre lo vinculado y lo cobrado/aportado."""
    groups: dict[int, list[ExpLink]] = defaultdict(list)
    for l in db.query(ExpLink).filter(ExpLink.status == status).order_by(ExpLink.exp_transaction_id, ExpLink.id):
        groups[l.exp_transaction_id].append(l)
    out = []
    for eid, links in groups.items():
        e = db.get(ExpTransaction, eid)
        amount = abs(e.amount_brl if e.amount_brl is not None else e.amount)
        linked = sum(l.amount_allocated_brl or 0 for l in links)
        out.append({
            "exp_transaction": {"id": e.id, "date": e.date.isoformat(), "description": e.description_raw,
                                "amount": e.amount, "currency": e.currency, "amount_brl": e.amount_brl, "kind": e.kind},
            "link_type": links[0].link_type, "difference_brl": round(linked - amount, 2),
            "links": [{"id": l.id, "target_type": l.target_type, "target_id": l.target_id, "label": l.target_label,
                       "date": l.target_date.isoformat() if l.target_date else None, "amount": l.target_amount,
                       "allocated": l.amount_allocated_brl, "score": l.score} for l in links]})
    return sorted(out, key=lambda g: g["exp_transaction"]["date"])


def audit_investments(db: Session, inv: Session, date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
    """Sólo lectura. (1) movimientos de inversión del extracto sin Transaction vinculada, (2) Transactions de
    custodias con cuenta importada sin movimiento bancario, (3) diferencias en vínculos confirmados."""
    def in_range(d):
        return (date_from is None or d >= date_from) and (date_to is None or d <= date_to)

    linked_exp = {i for (i,) in db.query(ExpLink.exp_transaction_id).filter(
        ExpLink.link_type == "investment", ExpLink.status.in_(ACTIVE))}
    linked_tx = _used_targets(db, "investment_transaction")
    bank_without = [
        {"id": e.id, "date": e.date.isoformat(), "description": e.description_raw, "amount": e.amount}
        for e in db.query(ExpTransaction).filter(
            ExpTransaction.kind.in_(("investment_contribution", "investment_withdrawal"))).order_by(ExpTransaction.date)
        if in_range(e.date) and e.id not in linked_exp]

    institutions = [a.institution.lower() for a in db.query(ExpAccount) if a.has_statements]
    inst = {i.id: i for i in inv.query(Instrument)}
    tx_without = []
    for t in inv.query(Transaction).filter(Transaction.type.in_(("aplicacion", "rescate"))).order_by(Transaction.date):
        i = inst.get(t.instrument_id)
        custodian = (i.custodian or "").lower() if i else ""
        if in_range(t.date) and t.id not in linked_tx and any(custodian and (custodian in x or x in custodian) for x in institutions):
            tx_without.append({"id": t.id, "date": t.date.isoformat(), "type": t.type, "amount_brl": t.amount_brl,
                               "instrument": i.name if i else None, "custodian": i.custodian if i else None})

    diffs, drift = [], []
    tx_by_id = {t.id: t for t in inv.query(Transaction)}
    confirmed: dict[int, list[ExpLink]] = defaultdict(list)
    for l in db.query(ExpLink).filter(ExpLink.link_type == "investment", ExpLink.status == "confirmed"):
        confirmed[l.exp_transaction_id].append(l)
        t = tx_by_id.get(l.target_id)
        if t is None or (l.target_amount is not None and abs(abs(t.amount_brl or 0) - l.target_amount) > 0.01) \
                or (l.target_date and t.date != l.target_date):
            drift.append({"link_id": l.id, "exp_transaction_id": l.exp_transaction_id, "label": l.target_label,
                          "reason": "la transacción de inversiones cambió o fue eliminada"})
    for eid, links in confirmed.items():
        e = db.get(ExpTransaction, eid)
        if not in_range(e.date):
            continue
        amount = abs(e.amount_brl if e.amount_brl is not None else e.amount)
        linked = sum(l.amount_allocated_brl or 0 for l in links)
        days = max(abs((l.target_date - e.date).days) for l in links if l.target_date) if any(l.target_date for l in links) else 0
        if abs(linked - amount) > 0.5 or days > 5:
            diffs.append({"exp_transaction_id": eid, "date": e.date.isoformat(), "bank_amount": amount, "linked_amount": round(linked, 2),
                          "difference": round(linked - amount, 2), "max_days_apart": days})
    return {"bank_movements_without_transaction": bank_without, "transactions_without_bank_movement": tx_without,
            "confirmed_link_differences": diffs, "drifted_links": drift}
