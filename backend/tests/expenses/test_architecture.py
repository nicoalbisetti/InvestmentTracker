"""Hace cumplir el límite del módulo (ver spec, decisión 1)."""
import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[2] / "app"
EXP = APP / "expenses"
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+(app(?:\.[\w]+)*)", re.M)


def _imports(path):
    return IMPORT_RE.findall(path.read_text(encoding="utf-8"))


def test_investments_never_import_expenses():
    for f in APP.rglob("*.py"):
        if EXP in f.parents or f.name == "main.py":
            continue
        assert not any(i.startswith("app.expenses") for i in _imports(f)), f


def test_only_linking_reads_investment_code():
    allowed = {EXP / "services" / "linking.py"}
    for f in EXP.rglob("*.py"):
        if f in allowed:
            continue
        bad = [i for i in _imports(f) if not i.startswith("app.expenses")]
        assert not bad, (f, bad)
