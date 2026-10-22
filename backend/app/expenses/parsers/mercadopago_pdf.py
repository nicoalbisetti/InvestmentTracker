"""Resumen de cuenta Mercado Pago (Argentina, PDF en pesos).

La descripción de cada movimiento se parte en varias líneas ARRIBA y ABAJO de la línea con fecha
(la fecha va centrada verticalmente en su celda). Las celdas están separadas por filetes finos, así
que las palabras se agrupan por celda usando coordenadas y no por orden del texto plano.
"""
import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import pdfplumber

from app.expenses.parsers._pdf import first_page_text, is_pdf, read_bytes
from app.expenses.parsers.base import Check, ParsedRow, ParsedStatement, ParseError
from app.expenses.parsers.numbers import parse_money

NUM = r"-?\d{1,3}(?:\.\d{3})*,\d{2}"
MONEY = rf"(?:US)?\$\s?{NUM}"
DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")
ID_RE = re.compile(r"^\d{9,}$")
ROW_TAIL = re.compile(rf"(\d{{9,}})\s+({MONEY})\s+({MONEY})(?:\s+.*)?$")
PERIOD_RE = re.compile(r"Per[ií]odo:\s*Del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.I)
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
DECLARED = ("Entradas", "Salidas", "Saldo inicial", "Saldo final")
TOL = Decimal("0.01")


def _lines(words, tol=3.0):
    """Agrupa palabras en líneas por cercanía vertical (top)."""
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(out[-1][0] - w["top"]) <= tol:
            out[-1][1].append(w)
        else:
            out.append([w["top"], [w]])
    return [(t, sorted(ws, key=lambda w: w["x0"])) for t, ws in out]


def parse_page_model(words, separators, desc_x_min=60.0):
    """words: dicts con text/x0/top; separators: 'top' de los filetes. Devuelve filas crudas.

    Cada celda entre dos filetes consecutivos con una línea de fecha es un movimiento.
    """
    seps = sorted(set(round(s, 1) for s in separators))
    rows = []
    for lo, hi in zip(seps, seps[1:]):
        cell = [w for w in words if lo <= w["top"] < hi]
        date_lines = [(t, ws) for t, ws in _lines(cell) if DATE_RE.match(ws[0]["text"]) and ws[0]["x0"] < desc_x_min]
        if not date_lines:
            continue
        t0, ws0 = date_lines[0]
        text = " ".join(w["text"] for w in ws0)
        m = ROW_TAIL.search(text)
        if not m:
            raise ParseError("Línea de movimiento ilegible")
        id_x0 = next(w["x0"] for w in ws0 if ID_RE.match(w["text"]))
        # orden vertical: lo que está arriba de la fecha, lo que comparte línea con ella y lo de abajo
        parts = [txt for txt in (
            " ".join(w["text"] for w in ws if desc_x_min <= w["x0"] < id_x0 - 1) for _, ws in _lines(cell)) if txt]
        rows.append({
            "date": ws0[0]["text"], "id": m.group(1), "amount": m.group(2), "balance": m.group(3),
            "lines": parts,
        })
    return rows


def _declared(text: str) -> dict:
    out = {}
    for k in DECLARED:
        m = re.search(rf"{k}:\s*({MONEY})", text)
        if m:
            out[k] = parse_money(m.group(1))
    return out


def _counterparty(lines: list[str]) -> Optional[str]:
    if lines and re.match(r"^Transferencia (recibida|enviada)", lines[0]) and len(lines) > 1:
        return lines[-1]
    return None


class MercadoPagoPdf:
    key = "mercadopago_pdf"

    def detect(self, filename: str, head_bytes: bytes) -> bool:
        if not is_pdf(head_bytes):
            return False
        t = first_page_text(head_bytes)
        return "RESUMEN DE CUENTA EN PESOS" in t and "DETALLE DE MOVIMIENTOS" in t

    def parse(self, path, **_) -> ParsedStatement:
        data = read_bytes(path)
        sections: dict[str, dict] = {}
        current = None
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if "RESUMEN DE CUENTA EN PESOS" in text:
                    current = "ARS"
                elif "RESUMEN DE TENENCIAS EN DÓLARES" in text:
                    current = "USD"
                if current is None:
                    continue
                sec = sections.setdefault(current, {"text": "", "raw": []})
                sec["text"] += text + "\n"
                seps = [r["top"] for r in page.rects if r["height"] < 2 and r["width"] > 40]
                sec["raw"] += parse_page_model(page.extract_words(), seps)
        if "ARS" not in sections:
            raise ParseError("No se encontró el resumen en pesos")

        rows: list[ParsedRow] = []
        checks: list[Check] = []
        decl_all: dict = {}
        period_text = sections["ARS"]["text"]
        for cur, sec in sections.items():
            sec_rows = [ParsedRow(
                date=datetime.strptime(r["date"], "%d-%m-%Y").date(), description_raw=" ".join(r["lines"]).strip(),
                amount=parse_money(r["amount"]), currency=cur, external_id=r["id"],
                counterparty=_counterparty(r["lines"]), balance_after=parse_money(r["balance"]),
            ) for r in sec["raw"]]
            rows += sec_rows
            checks += self._checks(cur, sec_rows, sec["text"], decl_all)

        p_start = p_end = None
        period = PERIOD_RE.search(period_text)
        if period and MONTHS.get(period.group(3).lower()):
            month, year = MONTHS[period.group(3).lower()], int(period.group(4))
            p_start, p_end = date(year, month, int(period.group(1))), date(year, month, int(period.group(2)))
        ars = [r for r in rows if r.currency == "ARS"]
        return ParsedStatement(
            parser_key=self.key, rows=rows, currencies=sorted(sections), period_start=p_start or (ars[0].date if ars else None),
            period_end=p_end or (ars[-1].date if ars else None), declared_totals=decl_all, validation=checks,
        )

    @staticmethod
    def _checks(cur: str, rows: list[ParsedRow], text: str, decl_all: dict) -> list[Check]:
        pre = "" if cur == "ARS" else f"{cur.lower()}_"
        decl = _declared(text)
        for k, v in decl.items():
            decl_all[f"{pre}{k.lower().replace(' ', '_')}"] = v
        checks = [Check(f"{pre}rows_found", bool(rows) or cur != "ARS", f"{len(rows)} filas"),
                  Check(f"{pre}descriptions_found", all(r.description_raw for r in rows), "todas las filas tienen descripción")]
        if len(decl) == 4:
            opening, closing = decl["Saldo inicial"], decl["Saldo final"]
            prev, breaks = opening, 0
            for r in rows:
                if abs(prev + r.amount - r.balance_after) > TOL:
                    breaks += 1
                prev = r.balance_after
            inc = sum((r.amount for r in rows if r.amount > 0), Decimal("0"))
            out = sum((r.amount for r in rows if r.amount < 0), Decimal("0"))
            checks += [
                Check(f"{pre}declared_totals_consistent", abs(opening + decl["Entradas"] + decl["Salidas"] - closing) <= TOL,
                      "saldo inicial + entradas + salidas = saldo final"),
                Check(f"{pre}running_balance", breaks == 0, f"{breaks} saltos de saldo"),
                Check(f"{pre}sum_inflows", abs(inc - decl["Entradas"]) <= TOL, "Σ entradas = declarado"),
                Check(f"{pre}sum_outflows", abs(out - decl["Salidas"]) <= TOL, "Σ salidas = declarado"),
                Check(f"{pre}closing_balance", abs((rows[-1].balance_after if rows else opening) - closing) <= TOL,
                      "saldo final = declarado"),
            ]
        else:
            checks.append(Check(f"{pre}declared_totals_found", False, "no se encontraron los totales declarados"))
        n_dates = len(re.findall(r"^\d{2}-\d{2}-\d{4}\s", text, re.M))
        checks.append(Check(f"{pre}all_date_lines_parsed", n_dates == len(rows), f"{n_dates} líneas con fecha, {len(rows)} filas"))
        return checks
