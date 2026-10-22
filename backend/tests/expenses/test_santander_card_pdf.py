import json
import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.expenses.parsers import detect_parser, get_parser
from tests.expenses.pdf_builder import build_pdf

REAL = pathlib.Path(__file__).resolve().parents[3] / "docs" / "expenses"
D = Decimal


def line(top, *, ymd=None, comp=None, flag=None, ref="", cuota=None, cash=None, tc=None, ars=None, usd=None, orig=None):
    """Una línea de movimiento con las columnas en sus posiciones x reales."""
    t = []
    if ymd:
        y, m, d = ymd
        if y:
            t.append((22, top, y))
        if m:
            t.append((36, top, m))
        t.append((74, top, d))
    if comp:
        t.append((89, top, comp))
    if flag:
        t.append((122, top, flag))
    t.append((137, top, ref))
    if cuota:
        t.append((271, top, cuota))
    if orig:
        t += [(262, top, orig[0]), (314, top, orig[1])]
    if cash:
        t.append((271, top, cash))
    if tc:
        t.append((329, top, tc))
    if ars:
        t.append((406, top, ars))
    if usd:
        t.append((530, top, usd))
    return t


def visa_pdf(prev=("1.000,00", "3,04"), body=None, total=("140,50", "3,07"), debit="$ 145,50 + U$S 3,07",
             brand="VISA", header="CIERRE 26 Feb 26VENCIMIENTO 09 Mar 26"):
    body = body if body is not None else default_body()
    p1 = [(313, 10, "RESUMEN DE CUENTA"), (57, 22, "Santander Río"), (366, 36, brand), (353, 206, header),
          (22, 150, "NOMBRE FICTICIO"), (22, 160, "CUIT 20-12345678-9"),
          (11, 314, "Fecha"), (79, 314, "Comprobante"), (133, 314, "Referencia"), (439, 314, "$"), (533, 314, "U$S"),
          (137, 330, "SALDO ANTERIOR"), (406, 330, prev[0]), (530, 330, prev[1])]
    p1 += body
    p1 += [(276, 572, "SALDO ACTUAL"), (406, 572, "$")]
    p2 = [(313, 10, "RESUMEN DE CUENTA"), (353, 206, header), (11, 314, "Fecha"), (79, 314, "Comprobante"),
          (133, 314, "Referencia"), (91, 556, f"DEBITAREMOS DE SU C.C.00000000000 LA SUMA DE {debit}"),
          (276, 572, "SALDO ACTUAL")]
    return build_pdf([{"texts": p1}, {"texts": p2}])


def default_body():
    b = []
    b += line(356, ymd=("26", "Febrero", "09"), ref="SU PAGO EN PESOS", cash="1.004,40", tc="TC1445,000", ars="1.000,00-", usd="3,04-")
    b += [(22, 366, "_" * 60)]
    b += line(374, ymd=("25", "Setiem.", "02"), comp="492500", flag="*", ref="COMERCIO UNO", cuota="C.06/06", ars="100,00")
    b += line(384, ymd=(None, None, "20"), comp="002013", flag="K", ref="COMERCIO DOS 5234567890123456", ars="50,50")
    b += line(392, ymd=("26", "Febrero", "02"), comp="133277", flag="E", ref="SPOTIFY", orig=("USD", "3,07"), usd="3,07")
    b += line(402, ymd=(None, None, "03"), comp="704435", flag="K", ref="DEVOLUCION", ars="10,00-")
    b += [(22, 416, "Tarjeta"), (60, 416, "8057"), (84, 416, "Total"), (113, 416, "Consumos"), (156, 416, "de NOMBRE"),
          (406, 416, "140,50"), (463, 416, "*"), (526, 416, "3,07"), (550, 416, "*")]
    b += line(430, ymd=("26", "Febrero", "26"), ref="IMPUESTO DE SELLOS", orig=("$", ""), ars="5,00")
    return b


@pytest.fixture
def pdf(tmp_path):
    def make(**kw):
        f = tmp_path / "r.pdf"; f.write_bytes(visa_pdf(**kw)); return f
    return make


def test_detect_visa_and_amex_by_content(pdf):
    assert detect_parser("x.pdf", pdf().read_bytes()).key == "santander_ar_card_pdf"
    assert detect_parser("x.pdf", pdf(brand="AMERICAN EXPRESS").read_bytes()).key == "santander_ar_card_pdf"
    assert detect_parser("x.pdf", build_pdf([{"texts": [(40, 40, "Mi resumen de cuenta")]}])) is None


def test_parse_synthetic_statement(pdf):
    st = get_parser("santander_ar_card_pdf").parse(pdf())
    assert st.checks_ok, [c for c in st.validation if not c.ok]
    assert (st.statement_due_date, st.statement_period, st.account_hint) == (date(2026, 3, 9), "2026-03", "VISA")
    assert st.declared_totals["ARS"] == D("145.50") and st.declared_totals["USD"] == D("3.07")
    pay = [r for r in st.rows if r.kind_hint == "card_payment"]
    assert len(pay) == 1 and pay[0].amount == D("1004.40") and pay[0].date == date(2026, 2, 9)  # pesos efectivamente debitados
    assert "TC1445,000" in pay[0].description_raw and pay[0].currency == "ARS"
    c1 = next(r for r in st.rows if r.description_raw == "COMERCIO UNO")
    assert (c1.amount, c1.date, c1.purchase_date, c1.installment_number, c1.installment_total) == (
        D("-100.00"), date(2026, 3, 9), date(2025, 9, 2), 6, 6)
    c2 = next(r for r in st.rows if r.description_raw.startswith("COMERCIO DOS"))
    assert c2.purchase_date == date(2025, 9, 20) and "5234567890123456" not in c2.description_raw and "***3456" in c2.description_raw
    sp = next(r for r in st.rows if r.description_raw == "SPOTIFY")
    assert (sp.currency, sp.amount, sp.purchase_date) == ("USD", D("-3.07"), date(2026, 2, 2))
    ref = next(r for r in st.rows if r.description_raw == "DEVOLUCION")
    assert ref.amount == D("10.00") and ref.kind_hint == "refund"
    tax = next(r for r in st.rows if r.description_raw == "IMPUESTO DE SELLOS")
    assert tax.amount == D("-5.00") and tax.date == date(2026, 3, 9)


def test_year_and_month_carry_across_lines(pdf):
    st = get_parser("santander_ar_card_pdf").parse(pdf())
    assert next(r for r in st.rows if r.description_raw.startswith("COMERCIO DOS")).purchase_date.month == 9


def test_multiple_partial_payments_without_cash_use_credit_amounts(pdf):
    body = (line(356, ymd=("26", "Febrero", "09"), ref="SU PAGO EN PESOS", ars="600,00-", usd="3,04-")
            + line(366, ymd=(None, None, "10"), ref="SU PAGO EN PESOS", ars="400,00-")
            + [(22, 380, "_" * 60)]
            + line(390, ymd=("26", "Febrero", "02"), comp="1", flag="*", ref="COMERCIO", ars="20,00")
            + [(22, 404, "Tarjeta"), (60, 404, "8057"), (84, 404, "Total"), (113, 404, "Consumos"), (406, 404, "20,00"),
               (526, 404, "0,00")])
    st = get_parser("santander_ar_card_pdf").parse(pdf(body=body, total=("20,00", "0,00"), debit="$ 20,00"))
    assert st.checks_ok, [c for c in st.validation if not c.ok]
    pays = sorted((r.currency, r.amount) for r in st.rows if r.kind_hint == "card_payment")
    assert pays == [("ARS", D("400.00")), ("ARS", D("600.00")), ("USD", D("3.04"))]


def test_debt_transfer_is_fx_conversion_not_spending(pdf):
    body = (line(356, ymd=("26", "Febrero", "09"), ref="TRANSFERENCIA DEUDA", orig=("", "3,08"), tc="TC1465,000", ars="4.512,20", usd="3,08-")
            + [(22, 380, "Tarjeta"), (60, 380, "8057"), (84, 380, "Total"), (113, 380, "Consumos"), (406, 380, "0,00"), (526, 380, "0,00")])
    f = pdf(prev=("0,00", "3,08"), body=body, total=("0,00", "0,00"), debit="$ 4.512,20")
    st = get_parser("santander_ar_card_pdf").parse(f)
    assert st.checks_ok, [c for c in st.validation if not c.ok]
    assert {r.kind_hint for r in st.rows} == {"fx_conversion"} and len(st.rows) == 2


def test_reconciliation_failures_are_detected(pdf):
    bad = get_parser("santander_ar_card_pdf").parse(pdf(debit="$ 999,00 + U$S 3,07"))
    assert "debit_ars" in {c.name for c in bad.validation if not c.ok}
    body = [(x, t, "150,00" if txt == "140,50" else txt) for x, t, txt in default_body()]
    bad2 = get_parser("santander_ar_card_pdf").parse(pdf(body=body))
    assert "total_consumos_ars" in {c.name for c in bad2.validation if not c.ok}


def test_no_identifiers_persisted(pdf):
    st = get_parser("santander_ar_card_pdf").parse(pdf())
    blob = json.dumps([c.__dict__ for c in st.validation]) + json.dumps([r.description_raw for r in st.rows])
    assert "12345678-9" not in blob and "NOMBRE FICTICIO" not in blob


real = pytest.mark.skipif(not REAL.exists(), reason="docs/expenses no disponible")


@real
def test_real_card_statements_all_green():
    files = sorted(REAL.glob("Resumen de tarjeta*.pdf"))
    if not files:
        pytest.skip("sin resúmenes de tarjeta")
    brands = set()
    for f in files:
        data = f.read_bytes()
        p = detect_parser(f.name, data)
        assert p is not None and p.key == "santander_ar_card_pdf", f.name
        st = p.parse(f)
        assert st.checks_ok, (f.name, [c for c in st.validation if not c.ok])
        brands.add(st.account_hint)
    assert brands == {"VISA", "AMEX"}
