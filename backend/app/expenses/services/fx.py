"""Tipos de cambio: PTAX venta (BCB) y dólar MEP (argentinadatos). Cache en exp_fx_rates.

- PTAX sólo trae días hábiles de Brasil: fines de semana/feriados -> último día previo.
- MEP viene por día calendario; igual se aplica forward fill por si falta algún día.
- Si no hay red, se usa el último valor conocido y la fila se marca fx_estimated.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import requests
from sqlalchemy.orm import Session

from app.expenses.models.fx_rate import PAIR_USDARS, PAIR_USDBRL, ExpFxRate

PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
    "?@dataInicial='{start}'&@dataFinalCotacao='{end}'&$format=json&$select=cotacaoVenda,dataHoraCotacao"
)
MEP_URL = "https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa"
MEP_FIELD = "venta"  # compra | venta
FETCH_TIMEOUT = 20
MAX_LOOKBACK_DAYS = 10

Fetcher = Callable[[str], object]


def _http_get_json(url: str):
    r = requests.get(url, timeout=FETCH_TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_ptax(start: date, end: date, fetch: Fetcher = _http_get_json) -> dict[date, float]:
    url = PTAX_URL.format(start=start.strftime("%m-%d-%Y"), end=end.strftime("%m-%d-%Y"))
    out: dict[date, float] = {}
    for row in fetch(url)["value"]:
        out[datetime.strptime(row["dataHoraCotacao"][:10], "%Y-%m-%d").date()] = float(row["cotacaoVenda"])
    return out


def fetch_mep(fetch: Fetcher = _http_get_json) -> dict[date, float]:
    return {
        datetime.strptime(r["fecha"], "%Y-%m-%d").date(): float(r[MEP_FIELD])
        for r in fetch(MEP_URL)
    }


def _store(db: Session, pair: str, source: str, rates: dict[date, float]) -> None:
    existing = {r.date: r for r in db.query(ExpFxRate).filter(ExpFxRate.pair == pair)}
    for d, v in rates.items():
        row = existing.get(d)
        if row is None:
            db.add(ExpFxRate(date=d, pair=pair, rate=v, source=source))
        elif row.source != "manual":  # la carga manual nunca se pisa
            row.rate, row.source = v, source
    db.commit()


def set_manual_rate(db: Session, pair: str, d: date, rate: float) -> None:
    row = db.get(ExpFxRate, (d, pair))
    if row:
        row.rate, row.source = rate, "manual"
    else:
        db.add(ExpFxRate(date=d, pair=pair, rate=rate, source="manual"))
    db.commit()


def _lookup(db: Session, pair: str, d: date) -> Optional[tuple[float, bool]]:
    """(rate, exact). exact=False si se usó un día anterior."""
    row = (
        db.query(ExpFxRate)
        .filter(ExpFxRate.pair == pair, ExpFxRate.date <= d, ExpFxRate.date >= d - timedelta(days=MAX_LOOKBACK_DAYS))
        .order_by(ExpFxRate.date.desc())
        .first()
    )
    if row is None:
        return None
    return row.rate, row.date == d


def refresh(db: Session, start: date, end: date, fetch: Fetcher = _http_get_json) -> list[str]:
    """Descarga y cachea ambas series. Devuelve errores (no levanta: se degrada a cache)."""
    errors = []
    try:
        _store(db, PAIR_USDBRL, "ptax", fetch_ptax(start - timedelta(days=MAX_LOOKBACK_DAYS), end, fetch))
    except Exception as e:  # noqa: BLE001
        errors.append(f"ptax: {type(e).__name__}")
    try:
        _store(db, PAIR_USDARS, "argentinadatos", fetch_mep(fetch))
    except Exception as e:  # noqa: BLE001
        errors.append(f"mep: {type(e).__name__}")
    return errors


def get_rate(db: Session, pair: str, d: date, fetch: Fetcher = _http_get_json) -> Optional[tuple[float, bool]]:
    """Devuelve (rate, estimated).

    Día exacto o forward fill (fin de semana/feriado, hasta MAX_LOOKBACK_DAYS) -> no estimado.
    Si no hay nada en cache se intenta refrescar; si la API falla se usa el último valor
    conocido marcado estimated; None si no existe ninguno.
    """
    hit = _lookup(db, pair, d)
    if hit is None or (not hit[1] and d > date.today() - timedelta(days=3)):
        refresh(db, d - timedelta(days=MAX_LOOKBACK_DAYS), d, fetch)
        hit = _lookup(db, pair, d)
    if hit is not None:
        return hit[0], False
    last = db.query(ExpFxRate).filter(ExpFxRate.pair == pair).order_by(ExpFxRate.date.desc()).first()
    return (last.rate, True) if last else None


@dataclass
class Converted:
    amount_brl: Optional[float]
    amount_usd: Optional[float]
    fx_usd_brl: Optional[float]
    fx_ars_usd: Optional[float]
    estimated: bool


def convert(db: Session, amount: float, currency: str, d: date, fetch: Fetcher = _http_get_json) -> Converted:
    """Convierte a BRL y USD. ARS->USD por MEP; USD/ARS->BRL por PTAX."""
    est = False
    ptax = get_rate(db, PAIR_USDBRL, d, fetch)
    mep = get_rate(db, PAIR_USDARS, d, fetch) if currency == "ARS" else None
    fx_usd_brl = ptax[0] if ptax else None
    fx_ars_usd = mep[0] if mep else None
    est = bool((ptax and ptax[1]) or (mep and mep[1]))
    if currency == "BRL":
        usd = amount / fx_usd_brl if fx_usd_brl else None
        return Converted(round(amount, 2), _r(usd), fx_usd_brl, None, est)
    if currency == "USD":
        brl = amount * fx_usd_brl if fx_usd_brl else None
        return Converted(_r(brl), round(amount, 2), fx_usd_brl, None, est)
    if currency == "ARS":
        usd = amount / fx_ars_usd if fx_ars_usd else None
        brl = usd * fx_usd_brl if (usd is not None and fx_usd_brl) else None
        return Converted(_r(brl), _r(usd), fx_usd_brl, fx_ars_usd, est)
    raise ValueError(f"Moneda no soportada: {currency}")


def _r(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(v, 2)
