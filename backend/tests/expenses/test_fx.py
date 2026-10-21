from datetime import date

import pytest

from app.expenses.models.fx_rate import PAIR_USDARS, PAIR_USDBRL
from app.expenses.services import fx

# Formas reales de respuesta (verificadas contra los endpoints el 2026-10-20), con importes inventados.
PTAX = {"value": [
    {"cotacaoVenda": 5.10, "dataHoraCotacao": "2026-04-02 13:10:26.9"},
    {"cotacaoVenda": 5.20, "dataHoraCotacao": "2026-04-06 13:06:24.727"},
]}
MEP = [
    {"casa": "bolsa", "compra": 1000.0, "venta": 1010.0, "fecha": "2026-04-02"},
    {"casa": "bolsa", "compra": 1100.0, "venta": 1110.0, "fecha": "2026-04-03"},
]


def fake_fetch(url):
    if "olinda" in url:
        assert "@dataInicial='" in url and "-2026" in url  # formato MM-DD-YYYY
        return PTAX
    return MEP


def down(url):
    raise ConnectionError("sin red")


def test_ptax_weekend_uses_previous_business_day(db):
    r = fx.get_rate(db, PAIR_USDBRL, date(2026, 4, 4), fake_fetch)  # sábado
    assert r == (5.10, False)  # 03/04 no existe en PTAX -> 02/04
    assert fx.get_rate(db, PAIR_USDBRL, date(2026, 4, 6), fake_fetch) == (5.20, False)


def test_convert_ars_via_mep_and_ptax(db):
    c = fx.convert(db, 101000.0, "ARS", date(2026, 4, 2), fake_fetch)
    assert c.fx_ars_usd == 1010.0 and c.fx_usd_brl == 5.10
    assert c.amount_usd == 100.0 and c.amount_brl == 510.0 and not c.estimated


def test_convert_brl_and_usd(db):
    b = fx.convert(db, 510.0, "BRL", date(2026, 4, 2), fake_fetch)
    assert (b.amount_brl, b.amount_usd) == (510.0, 100.0)
    u = fx.convert(db, 100.0, "USD", date(2026, 4, 2), fake_fetch)
    assert (u.amount_brl, u.amount_usd) == (510.0, 100.0)


def test_api_down_uses_last_known_and_flags_estimated(db):
    fx.refresh(db, date(2026, 4, 1), date(2026, 4, 7), fake_fetch)
    r = fx.get_rate(db, PAIR_USDBRL, date(2026, 9, 1), down)
    assert r == (5.20, True)
    assert fx.get_rate(db, PAIR_USDARS, date(2026, 9, 1), down) == (1110.0, True)


def test_no_data_at_all_returns_none(db):
    assert fx.get_rate(db, PAIR_USDBRL, date(2026, 4, 2), down) is None
    c = fx.convert(db, 10.0, "BRL", date(2026, 4, 2), down)
    assert c.amount_usd is None


def test_manual_rate_not_overwritten_by_refresh(db):
    fx.set_manual_rate(db, PAIR_USDBRL, date(2026, 4, 2), 9.99)
    fx.refresh(db, date(2026, 4, 1), date(2026, 4, 7), fake_fetch)
    assert fx.get_rate(db, PAIR_USDBRL, date(2026, 4, 2), fake_fetch) == (9.99, False)


def test_unsupported_currency(db):
    with pytest.raises(ValueError):
        fx.convert(db, 1.0, "EUR", date(2026, 4, 2), fake_fetch)
