import json
import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.expenses.parsers import detect_parser, get_parser
from tests.expenses.pdf_builder import build_pdf

REAL = pathlib.Path(__file__).resolve().parents[3] / "docs" / "expenses"
D = Decimal


def santander_pdf(tweak=None) -> bytes:
    cover = {"texts": [
        (23, 91, "Cuenta 000-000000/0"), (513, 104, "Período"), (482, 129, "Desde: 27/02/26"), (482, 142, "Hasta: 28/03/26"),
        (23, 30, "Mi resumen de cuenta"), (23, 50, "NOMBRE FICTICIO"), (23, 60, "CUIT: 20-12345678-9"),
        (23, 70, "CBU: 0000000000000000000000"), (27, 135, "Saldo total al 28/03/26*"),
    ]}
    texts = [(23, 302, "Movimientos en pesos"),
             (28, 337, "Fecha"), (70, 337, "Comprobante"), (120, 337, "Movimiento"), (337, 337, "Caja de Ahorro en pesos"),
             (417, 337, "Cuenta Corriente en pesos"), (500, 337, "Saldo en cuenta")]
    boxes = [(23, 327, 40, 24), (65, 327, 48, 24), (115, 327, 210, 24), (327, 327, 82, 24), (411, 327, 84, 24), (497, 327, 82, 24)]
    rules = [(23, y, 556) for y in (371, 401, 431, 461, 491)]
    texts += [  # Saldo inicial (fecha en la misma línea)
        (23, 358, "27/02/26"), (115, 358, "Saldo Inicial"), (357, 358, "$ 100,00"), (468, 358, "$ 0,00"), (527, 358, "$ 100,00"),
        # A: fecha en la línea principal, detalle abajo
        (23, 378, "27/02/26"), (65, 378, "1234567"), (115, 378, "Compra con tarjeta de debito"), (359, 378, "-$ 10,00"),
        (528, 378, "$ 90,00"), (115, 390, "Comercio Uno - tarj nro. 6118"),
        # B: fecha centrada entre la línea principal y el detalle
        (65, 408, "2345678"), (115, 408, "Transferencia recibida"), (362, 408, "$ 50,00"), (528, 408, "$ 140,00"),
        (23, 414, "28/02/26"), (115, 419, "De Tercero Ficticio / varios - var / 2 20123456789"),
        # C: sin comprobante, con línea de período de intereses entre el detalle
        (23, 438, "01/03/26"), (115, 438, "Comision por servicio"), (364, 438, "-$ 5,00"), (528, 438, "$ 135,00"),
        (115, 450, "Del 01/02/26 al 28/02/26"), (115, 456, "Adhesion programa"),
        # D: importe en la columna de cuenta corriente, nº de tarjeta largo en el detalle
        (65, 468, "3456789"), (115, 468, "Pago de servicios"), (450, 468, "-$ 20,00"), (528, 468, "$ 115,00"),
        (23, 474, "01/03/26"), (115, 479, "Mastercard: 5234567890123456"),
        (23, 520, "Saldo total $ 115,00"), (23, 540, "Movimientos en dólares"),
        (23, 552, "No tenés movimientos en dólares en este período."),
    ]
    table = {"texts": texts, "rules": rules, "boxes": boxes}
    consumos = {"texts": [(23, 40, "Fecha Comprobante Descripción Cuota Pesos Dólares"),
                          (23, 60, "05/03/26 836735 Merpago/shellbox $ 53.002,56 $ 999,00")]}
    if tweak:
        tweak(table)
    return build_pdf([cover, table, consumos])


@pytest.fixture
def pdf_file(tmp_path):
    f = tmp_path / "x.pdf"; f.write_bytes(santander_pdf())
    return f


def test_detect_by_content(pdf_file):
    assert detect_parser("x.pdf", pdf_file.read_bytes()).key == "santander_ar_account_pdf"


def test_parse_synthetic(pdf_file):
    st = get_parser("santander_ar_account_pdf").parse(pdf_file)
    assert st.checks_ok, [c for c in st.validation if not c.ok]
    assert (st.period_start, st.period_end) == (date(2026, 2, 27), date(2026, 3, 28))
    r = st.rows
    assert [x.amount for x in r] == [D("-10.00"), D("50.00"), D("-5.00"), D("-20.00")]  # opening y consumos de tarjeta fuera
    assert [x.date for x in r] == [date(2026, 2, 27), date(2026, 2, 28), date(2026, 3, 1), date(2026, 3, 1)]
    assert [x.external_id for x in r] == ["1234567", "2345678", None, "3456789"]
    assert r[1].description_raw.startswith("Transferencia recibida De Tercero Ficticio")
    assert r[1].counterparty == "Tercero Ficticio"
    assert "Del 01/02/26" not in r[2].description_raw and r[2].description_raw.endswith("Adhesion programa")
    assert r[3].amount == D("-20.00") and r[3].balance_after == D("115.00")  # columna cuenta corriente


def test_long_numbers_are_masked(pdf_file):
    st = get_parser("santander_ar_account_pdf").parse(pdf_file)
    blob = json.dumps([x.description_raw for x in st.rows]) + json.dumps([c.__dict__ for c in st.validation])
    assert "5234567890123456" not in blob and "20123456789" not in blob and "***3456" in blob and "12345678-9" not in blob


def test_broken_chain_detected(tmp_path):
    def tweak(t):
        t["texts"] = [(x, y, "$ 141,00" if s == "$ 140,00" else s) for x, y, s in t["texts"]]
    f = tmp_path / "b.pdf"; f.write_bytes(santander_pdf(tweak))
    st = get_parser("santander_ar_account_pdf").parse(f)
    assert not st.checks_ok and "running_balance" in {c.name for c in st.validation if not c.ok}


def test_closing_mismatch_detected(tmp_path):
    def tweak(t):
        t["texts"] = [(x, y, "Saldo total $ 116,00" if s.startswith("Saldo total") else s) for x, y, s in t["texts"]]
    f = tmp_path / "c.pdf"; f.write_bytes(santander_pdf(tweak))
    assert "closing_balance" in {c.name for c in get_parser("santander_ar_account_pdf").parse(f).validation if not c.ok}


def test_other_pdf_not_detected():
    assert detect_parser("x.pdf", build_pdf([{"texts": [(40, 40, "Mi resumen de cuenta de otro banco")]}])) is None


real = pytest.mark.skipif(not REAL.exists(), reason="docs/expenses no disponible")


@real
def test_real_statements_green_and_contiguous():
    files = sorted(REAL.glob("20*_0072*.pdf"))
    if not files:
        pytest.skip("sin extractos Santander")
    prev_close = None
    for f in files:
        data = f.read_bytes()
        p = detect_parser(f.name, data)
        assert p is not None and p.key == "santander_ar_account_pdf", f.name
        st = p.parse(f)
        assert st.checks_ok, (f.name, [c for c in st.validation if not c.ok])
        opening = st.rows[0].balance_after - st.rows[0].amount
        if prev_close is not None:
            assert abs(opening - prev_close) < D("0.01")  # el cierre de un mes es la apertura del siguiente
        prev_close = st.rows[-1].balance_after
        assert not any(__import__("re").search(r"\d{8,}", x.description_raw) for x in st.rows)
