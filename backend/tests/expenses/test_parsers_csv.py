import json
import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.expenses.parsers import NeedsDueDate, detect_parser, get_parser
from app.expenses.parsers.numbers import parse_money

FIX = pathlib.Path(__file__).parent / "fixtures"
REAL = pathlib.Path(__file__).resolve().parents[3] / "docs" / "expenses"
GOLDEN = pathlib.Path(__file__).parent / "real_golden.json"  # gitignored


def D(x):
    return Decimal(x)


# --- números ---
@pytest.mark.parametrize("raw,expected", [
    ("R$ 1.234,56", "1234.56"), ("-R$ 1.234,56", "-1234.56"), ("-$ 26.555,51", "-26555.51"),
    ("$ -565.200,00", "-565200.00"), ("1672.047,98-", "-1672047.98"), ("1672047,98", "1672047.98"),
    ("$ 103.091 80", "103091.80"), ("0,00", "0.00"), ("U$S 3,15", "3.15"),
])
def test_parse_money(raw, expected):
    assert parse_money(raw) == D(expected)


@pytest.mark.parametrize("raw", [None, "", "-", "abc"])
def test_parse_money_invalid(raw):
    assert parse_money(raw) is None


# --- detect ---
def test_detect_each_fixture():
    for name, key in [("xp_account_sample.csv", "xp_account_csv"),
                      ("xp_card_sample_Fatura2026-03-20.csv", "xp_card_csv"),
                      ("inter_account_sample.csv", "inter_account_csv")]:
        p = detect_parser(name, (FIX / name).read_bytes()[:2048])
        assert p is not None and p.key == key


def test_detect_unknown():
    assert detect_parser("x.csv", b"a,b,c\n1,2,3") is None


# --- xp_card_csv ---
def test_xp_card_sample():
    st = get_parser("xp_card_csv").parse(FIX / "xp_card_sample_Fatura2026-03-20.csv")
    assert st.statement_due_date == date(2026, 3, 20) and st.statement_period == "2026-03"
    assert st.checks_ok and len(st.rows) == 8
    easy = [r for r in st.rows if "EASYJET" in r.description_raw]
    assert len(easy) == 3 and sum(1 for r in easy if r.amount == D("10.00")) == 2  # no se deduplican
    inst = next(r for r in st.rows if r.description_raw == "LOJA EXEMPLO")
    assert (inst.installment_number, inst.installment_total, inst.purchase_date) == (3, 6, date(2025, 12, 10))
    assert inst.date == date(2026, 3, 20)
    assert next(r for r in st.rows if r.description_raw == "MERCADO EXEMPLO").installment_total is None  # ' de 1'
    assert next(r for r in st.rows if r.description_raw == "ESTORNO COMERCIO").kind_hint == "refund"
    pay = next(r for r in st.rows if r.kind_hint == "card_payment")
    assert pay.amount == D("-50.00")
    # total sin el pago: 10+10+3.30+100+20+5-7
    assert st.declared_totals["statement_total"] == D("141.30")
    assert st.declared_totals["previous_payment"] == D("-50.00")


def test_xp_card_due_date_required_when_filename_unknown(tmp_path):
    f = tmp_path / "export.csv"
    f.write_bytes((FIX / "xp_card_sample_Fatura2026-03-20.csv").read_bytes())
    p = get_parser("xp_card_csv")
    with pytest.raises(NeedsDueDate):
        p.parse(f)
    assert p.parse(f, due_date=date(2026, 4, 20)).statement_period == "2026-04"


# --- inter ---
def test_inter_sample():
    st = get_parser("inter_account_csv").parse(FIX / "inter_account_sample.csv")
    assert st.checks_ok and len(st.rows) == 4
    assert (st.period_start, st.period_end) == (date(2026, 1, 1), date(2026, 1, 31))
    assert [r.counterparty for r in st.rows] == ["Titular Ficticio", "EMPRESA EXEMPLO LTDA", "BANCO INTER SA", None]
    assert st.rows[0].amount == D("-100.00")
    assert "000000000" not in json.dumps([c.__dict__ for c in st.validation])  # sin nº de cuenta


def test_inter_detects_broken_balance(tmp_path):
    text = (FIX / "inter_account_sample.csv").read_text().replace("1.150,00", "1.151,00")
    f = tmp_path / "i.csv"; f.write_text(text)
    st = get_parser("inter_account_csv").parse(f)
    assert not st.checks_ok


# --- xp cuenta ---
def test_xp_account_orders_ties_by_balance_chain():
    st = get_parser("xp_account_csv").parse(FIX / "xp_account_sample.csv")
    assert st.checks_ok, st.validation
    descs = [r.description_raw for r in st.rows]
    # En el empate 10:00:00 el archivo (descendente) trae LIQ antes que Pix, pero cronológicamente
    # LIQ ocurre primero: invertir el archivo rompería el saldo; la cadena lo resuelve.
    assert descs[0].startswith("Transferência") and descs[2].startswith("LIQ") and descs[3].startswith("Pix enviado")
    assert [r.balance_after for r in st.rows][-1] == D("70.00")
    assert st.declared_totals["opening_balance"] == D("0.00")
    assert st.rows[1].time == "08:00:00" and st.rows[1].date == date(2026, 3, 10)


# --- archivos reales (se saltean si no existen) ---
real = pytest.mark.skipif(not REAL.exists(), reason="docs/expenses no disponible")


@real
def test_real_files_all_checks_green_and_detected():
    parsed = 0
    for f in sorted(REAL.glob("*.csv")):
        p = detect_parser(f.name, f.read_bytes()[:2048])
        assert p is not None, f.name
        st = p.parse(f)
        assert st.checks_ok, (f.name, [c for c in st.validation if not c.ok])
        parsed += 1
    assert parsed >= 1


@real
def test_real_golden_values():
    if not GOLDEN.exists():
        pytest.skip("real_golden.json no disponible")
    g = json.loads(GOLDEN.read_text())
    for name, exp in g.get("xp_card", {}).items():
        st = get_parser("xp_card_csv").parse(REAL / name)
        assert st.declared_totals["statement_total"] == D(exp["statement_total"])
        assert st.declared_totals["previous_payment"] == D(exp["previous_payment"])
        for desc, count in exp.get("identical_rows", {}).items():
            assert sum(1 for r in st.rows if r.description_raw.startswith(desc) and str(r.amount) == "10.00") == count
