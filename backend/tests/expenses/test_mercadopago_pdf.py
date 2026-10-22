import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.expenses.parsers import detect_parser, get_parser
from tests.expenses.pdf_builder import build_pdf

REAL = pathlib.Path(__file__).resolve().parents[3] / "docs" / "expenses"
D = Decimal


def mp_pdf(tweak=None) -> bytes:
    """Resumen sintético: 3 movimientos (uno con descripción en 2 líneas arriba y abajo) + sección en dólares."""
    head = [
        (40, 40, "RESUMEN DE CUENTA EN PESOS"), (40, 52, "Periodo: Del 1 al 30 de abril de 2026"),
        (40, 64, "Entradas: $ 1.500,00"), (40, 76, "Saldo inicial: $ 100,00 Saldo final: $ 1.000,00"),
        (40, 88, "Salidas: $ -600,00"), (40, 160, "DETALLE DE MOVIMIENTOS"),
    ]
    col = lambda top, date_, id_, amt, bal: [(40, top, date_), (197, top, id_), (260, top, amt), (360, top, bal)]
    texts = head + [(40, 185, "Fecha"), (89, 185, "Descripción")]
    rules = [(40, y, 360) for y in (202, 232, 262, 297, 332)]
    # fila 1: una línea
    texts += [(89, 214, "Rendimientos")] + col(215, "01-04-2026", "111111111111", "$ 4,00", "$ 104,00")
    # fila 2: texto arriba y abajo de la fecha
    texts += [(89, 244, "Transferencia recibida Julio")] + col(247, "06-04-2026", "222222222222", "$ 1.496,00", "$ 1.600,00") + [(89, 256, "Tercero Ficticio")]
    # fila 3: negativa, 3 líneas
    texts += [(89, 270, "Pago de servicio Empresa"), (89, 280, "SIRO")] + col(283, "07-04-2026", "333333333333", "$ -600,00", "$ 1.000,00") + [(89, 290, "Servicio")]
    pdf1 = {"texts": texts, "rules": rules[:4]}
    pdf2 = {"texts": [
        (40, 40, "RESUMEN DE TENENCIAS EN DÓLARES"), (40, 52, "Periodo: Del 1 al 30 de abril de 2026"),
        (40, 64, "Entradas: US$ 0,01"), (40, 76, "Saldo inicial: US$ 1,13 Saldo final: US$ 1,14"), (40, 88, "Salidas: US$ 0,00"),
        (40, 160, "DETALLE DE MOVIMIENTOS DEL PERIODO"), (33, 185, "Fecha"),
        (33, 215, "17-04-2026"), (80, 214, "Rendimientos"), (147, 215, "444444444444"), (221, 215, "US$ 0,01"), (388, 215, "US$ 1,14"),
    ], "rules": [(33, 202, 46), (80, 202, 48), (147, 202, 55), (33, 232, 46), (80, 232, 48), (147, 232, 55)]}
    if tweak:
        tweak(pdf1, pdf2)
    return build_pdf([pdf1, pdf2])


@pytest.fixture
def mp_file(tmp_path):
    f = tmp_path / "estado.pdf"; f.write_bytes(mp_pdf())
    return f


def test_detect_by_content_not_name(mp_file):
    assert detect_parser("cualquier-nombre.bin", mp_file.read_bytes()).key == "mercadopago_pdf"
    assert detect_parser("x.pdf", build_pdf([{"texts": [(40, 40, "otro documento")]}])) is None


def test_parse_synthetic(mp_file):
    st = get_parser("mercadopago_pdf").parse(mp_file)
    assert st.checks_ok, [c for c in st.validation if not c.ok]
    assert (st.period_start, st.period_end) == (date(2026, 4, 1), date(2026, 4, 30))
    ars = [r for r in st.rows if r.currency == "ARS"]
    assert [r.description_raw for r in ars] == [
        "Rendimientos", "Transferencia recibida Julio Tercero Ficticio", "Pago de servicio Empresa SIRO Servicio"]
    assert [r.amount for r in ars] == [D("4.00"), D("1496.00"), D("-600.00")]
    assert ars[1].counterparty == "Tercero Ficticio" and ars[0].counterparty is None
    assert ars[1].external_id == "222222222222" and ars[1].balance_after == D("1600.00")
    usd = [r for r in st.rows if r.currency == "USD"]
    assert len(usd) == 1 and usd[0].amount == D("0.01") and usd[0].description_raw == "Rendimientos"
    assert st.currencies == ["ARS", "USD"]


def test_broken_balance_is_detected(tmp_path):
    def tweak(p1, p2):
        p1["texts"] = [(x, t, "$ 999,00" if s == "$ 1.000,00" else s) for x, t, s in p1["texts"]]
    f = tmp_path / "e.pdf"; f.write_bytes(mp_pdf(tweak))
    st = get_parser("mercadopago_pdf").parse(f)
    assert not st.checks_ok
    assert {c.name for c in st.validation if not c.ok} >= {"running_balance"}


def test_declared_totals_mismatch_is_detected(tmp_path):
    def tweak(p1, p2):
        p1["texts"] = [(x, t, "Entradas: $ 9.500,00" if s.startswith("Entradas") else s) for x, t, s in p1["texts"]]
    f = tmp_path / "e.pdf"; f.write_bytes(mp_pdf(tweak))
    assert not get_parser("mercadopago_pdf").parse(f).checks_ok


def test_no_identifiers_in_validation(mp_file):
    import json
    st = get_parser("mercadopago_pdf").parse(mp_file)
    assert "Comitente" not in json.dumps([c.__dict__ for c in st.validation])


real = pytest.mark.skipif(not REAL.exists(), reason="docs/expenses no disponible")


@real
def test_real_mercadopago_files_all_green():
    files = sorted(REAL.glob("MercadoPago-*.pdf"))
    if not files:
        pytest.skip("sin PDFs de Mercado Pago")
    total = 0
    for f in files:
        data = f.read_bytes()
        p = detect_parser(f.name, data)
        assert p is not None and p.key == "mercadopago_pdf", f.name
        st = p.parse(f)
        assert st.checks_ok, (f.name, [c for c in st.validation if not c.ok])
        total += len(st.rows)
    assert total > 0
