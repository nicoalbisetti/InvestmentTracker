"""Conciliación interna: pares de transferencias, pagos de fatura y cobertura de tarjetas.

Los vínculos internos viven en columnas de exp_transactions (transfer_group_id, statement_batch_id).
La conciliación con inversiones/proventos (lectura de tablas de inversiones) se agrega en este mismo
módulo en una etapa posterior: es el único lugar donde se permite importar código de inversiones.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.expenses.models import ExpAccount, ExpImportBatch, ExpTransaction
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
