import csv
import io
from datetime import date, datetime


def read_text(path) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("utf-8-sig")


def dict_rows(text: str):
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def parse_date(s: str) -> date:
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha inválida: {s!r}")
