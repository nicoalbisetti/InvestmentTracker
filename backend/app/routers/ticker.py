from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models.instrument import Instrument

router = APIRouter(prefix="/api/ticker", tags=["ticker"])

_TICKER_CACHE: dict = {}
TICKER_CACHE_TTL = 300  # 5 minutos


def _get_cached() -> dict | None:
    if "data" in _TICKER_CACHE and datetime.utcnow() < _TICKER_CACHE["expires_at"]:
        return _TICKER_CACHE["data"]
    return None


def _set_cache(data: dict):
    _TICKER_CACHE["data"] = data
    _TICKER_CACHE["expires_at"] = datetime.utcnow() + timedelta(seconds=TICKER_CACHE_TTL)


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return " ".join(parts[:3])


def _get_equity_tickers(db: Session) -> list[dict]:
    """Retorna instrumentos activos de tipo accion/fii con ticker definido."""
    instruments = (
        db.query(Instrument)
        .filter(
            Instrument.type.in_(["accion", "fii"]),
            Instrument.status == "activo",
            Instrument.ticker.isnot(None),
            Instrument.ticker != "",
        )
        .all()
    )
    return [
        {
            "id": inst.id,
            "ticker": inst.ticker,
            "name": inst.name,
            "currency": inst.currency or "BRL",
        }
        for inst in instruments
    ]


@router.get("/quotes")
def get_ticker_quotes(db: Session = Depends(get_db)):
    now = datetime.utcnow()

    cached = _get_cached()
    if cached:
        return {**cached, "cached": True}

    instruments = _get_equity_tickers(db)

    if not instruments:
        result = {"items": [], "fetched_at": now.isoformat(), "cached": False}
        _set_cache(result)
        return result

    # Construir mapa yfinance_ticker -> instrumento
    yf_map: dict[str, dict] = {}
    for inst in instruments:
        currency = inst["currency"]
        yf_ticker = inst["ticker"] + ".SA" if currency == "BRL" else inst["ticker"]
        yf_map[yf_ticker] = inst

    try:
        import yfinance as yf
        import pandas as pd

        tickers_list = list(yf_map.keys())
        data = yf.download(
            tickers=" ".join(tickers_list),
            period="2d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )

        items = []
        for yf_ticker, inst in yf_map.items():
            try:
                if len(tickers_list) == 1:
                    closes = data["Close"]
                else:
                    closes = data[yf_ticker]["Close"]

                closes = closes.dropna()
                if len(closes) == 0:
                    continue

                price = float(closes.iloc[-1])
                if len(closes) >= 2:
                    prev = float(closes.iloc[-2])
                    change_pct = (price - prev) / prev * 100 if prev != 0 else 0.0
                else:
                    change_pct = 0.0

                items.append({
                    "ticker": inst["ticker"],
                    "name": _short_name(inst["name"]),
                    "price": round(price, 2),
                    "change_pct": round(change_pct, 2),
                    "currency": inst["currency"],
                })
            except Exception as e:
                print(f"[ticker] Error procesando {yf_ticker}: {e}")
                continue

        result = {"items": items, "fetched_at": now.isoformat(), "cached": False}
        _set_cache(result)
        return result

    except Exception as e:
        print(f"[ticker] yfinance no disponible: {e}")
        # Best-effort: devolver cache expirado si existe
        if _TICKER_CACHE.get("data"):
            return {**_TICKER_CACHE["data"], "cached": True, "stale": True}
        return {"items": [], "fetched_at": now.isoformat(), "cached": False, "error": "yfinance unavailable"}
