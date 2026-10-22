"""Extracto de cuenta Santander Argentina (PDF).

La tabla de movimientos tiene celdas separadas por filetes finos. Dentro de cada celda la fecha va
centrada verticalmente (puede quedar antes, al lado o entre la línea principal y el detalle), por eso
las palabras se agrupan por celda con coordenadas y cada dato se toma por su columna, no por el orden
del texto plano. Las páginas de detalle de tarjetas (consumos del resumen de crédito) no se leen acá.

Privacidad: los números largos (CUIT, CBU, nº de tarjeta, nº de cuenta) se enmascaran en las
descripciones; el comprobante (external_id) viene de su propia columna.
"""
import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import pdfplumber

from app.expenses.parsers._pdf import first_page_text, is_pdf, read_bytes
from app.expenses.parsers.base import Check, ParsedRow, ParsedStatement, ParseError
from app.expenses.parsers.mercadopago_pdf import _lines
from app.expenses.parsers.numbers import parse_money

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{2}$")
LONG_NUM = re.compile(r"\d{8,}")
INTEREST_PERIOD = re.compile(r"^Del \d{2}/\d{2}/\d{2} al \d{2}/\d{2}/\d{2}$")
COUNTERPARTY = re.compile(r"^(?:A|De)\s+(.+?)\s*/")
TOL = Decimal("0.01")
MONEY = r"(?:-?(?:U\$S|\$)\s?-?\d{1,3}(?:\.\d{3})*,\d{2})"


def mask(text: str) -> str:
    return LONG_NUM.sub(lambda m: "***" + m.group()[-4:], text)


def _d(s: str) -> date:
    return datetime.strptime(s, "%d/%m/%y").date()


def _columns(page) -> Optional[dict]:
    """x de arranque de cada columna, tomado de las celdas del encabezado (o de las palabras)."""
    words = page.extract_words()
    comp = next((w for w in words if w["text"] == "Comprobante"), None)
    if comp is None or not any(w["text"] == "Movimiento" and abs(w["top"] - comp["top"]) < 3 for w in words):
        return None
    heads = sorted(
        r["x0"] for r in page.rects if 15 < r["height"] < 40 and abs(r["top"] - (comp["top"] - 10)) < 25 and r["width"] > 30)
    if len(heads) >= 6:
        return {"top": comp["top"], "mov": heads[2], "caja": heads[3], "cc": heads[4], "saldo": heads[5],
                "bottom_of_header": max(r["top"] + r["height"] for r in page.rects
                                        if 15 < r["height"] < 40 and abs(r["top"] - (comp["top"] - 10)) < 25)}
    caja = next(w for w in words if w["text"] == "Caja")["x0"]
    cc = next(w for w in words if w["text"] == "Cuenta" and w["x0"] > caja)["x0"]
    return {"top": comp["top"], "mov": 115.0, "caja": caja - 10, "cc": cc - 6, "saldo": cc + 80,
            "bottom_of_header": comp["top"] + 14}


def _markers(page):
    """[(top, 'ARS'|'USD')] de los títulos 'Movimientos en pesos/dólares' y el límite de la tabla."""
    out, limit = [], None
    for top, ws in _lines(page.extract_words()):
        text = " ".join(w["text"] for w in ws)
        if ws[0]["x0"] < 40 and text.lower().startswith("movimientos en pesos"):
            out.append((top, "ARS"))
        elif ws[0]["x0"] < 40 and text.lower().startswith("movimientos en d"):
            out.append((top, "USD"))
        if text.startswith("Saldo total") and "$" in text and limit is None:
            limit = top
    return out, limit


def parse_cell(words, cols) -> Optional[dict]:
    """Interpreta una celda. None si no tiene línea principal (con saldo)."""
    lines = _lines(words)
    main = None
    for top, ws in lines:
        if any(w["x0"] >= cols["saldo"] - 2 and re.search(r"\d,\d{2}$", w["text"]) for w in ws):
            main = (top, ws); break
    if main is None:
        return None
    mtop, mws = main
    dates = [w["text"] for _, ws in lines for w in ws if w["x0"] < 62 and DATE_RE.match(w["text"])]
    comp = next((w["text"] for w in mws if 62 <= w["x0"] < cols["mov"] - 2 and re.match(r"^\d{3,}$", w["text"])), None)
    title = " ".join(w["text"] for w in mws if cols["mov"] - 2 <= w["x0"] < cols["caja"] - 2)

    def amount(lo, hi):
        txt = " ".join(w["text"] for w in mws if lo <= w["x0"] < hi)
        return re.sub(r"\s+", " ", txt).strip()

    caja, cc, saldo = amount(cols["caja"] - 2, cols["cc"] - 2), amount(cols["cc"] - 2, cols["saldo"] - 2), amount(cols["saldo"] - 2, 1e9)
    details = []
    for top, ws in lines:
        if top == mtop:
            continue
        txt = " ".join(w["text"] for w in ws if w["x0"] >= cols["mov"] - 2)
        if txt and not INTEREST_PERIOD.match(txt):
            details.append(txt)
    return {"date": dates[0] if dates else None, "comp": comp, "title": title, "caja": caja, "cc": cc,
            "saldo": saldo, "details": details}


class SantanderArAccountPdf:
    key = "santander_ar_account_pdf"

    def detect(self, filename: str, head_bytes: bytes) -> bool:
        if not is_pdf(head_bytes):
            return False
        t = first_page_text(head_bytes)
        return "Mi resumen de cuenta" in t and "Desde:" in t and "Hasta:" in t and "VENCIMIENTO" not in t

    def parse(self, path, **_) -> ParsedStatement:
        data = read_bytes(path)
        current = "ARS"
        sections: dict[str, dict] = {}
        p_start = p_end = None
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            head = pdf.pages[0].extract_text() or ""
            m1, m2 = re.search(r"Desde:\s*(\d{2}/\d{2}/\d{2})", head), re.search(r"Hasta:\s*(\d{2}/\d{2}/\d{2})", head)
            if m1 and m2:
                p_start, p_end = _d(m1.group(1)), _d(m2.group(1))
            for page in pdf.pages:
                cols = _columns(page)
                if cols is None:
                    continue
                markers, limit = _markers(page)
                words = page.extract_words()
                seps = sorted(round(r["top"], 1) for r in page.rects if r["height"] <= 1 and r["width"] > 400)
                bottom = limit if limit is not None else page.height
                bounds = [cols["bottom_of_header"]] + [s for s in seps if cols["bottom_of_header"] < s < bottom] + [bottom]
                for lo, hi in zip(bounds, bounds[1:]):
                    for top, cur in markers:
                        if top < lo:
                            current = cur
                    sec = sections.setdefault(current, {"cells": [], "bad": 0, "closing": None})
                    cell_words = [w for w in words if lo <= w["top"] < hi]
                    if not cell_words:
                        continue
                    c = parse_cell(cell_words, cols)
                    if c is None:
                        if any(DATE_RE.match(w["text"]) or re.search(r"\d,\d{2}$", w["text"]) for w in cell_words):
                            sec["bad"] += 1
                        continue
                    sec["cells"].append(c)
                if limit is not None:
                    line = next((" ".join(w["text"] for w in ws) for t, ws in _lines(words) if t == limit), "")
                    mm = re.search(rf"({MONEY})\s*$", line)
                    sections.setdefault(current, {"cells": [], "bad": 0, "closing": None})["closing"] = parse_money(mm.group(1)) if mm else None

        rows: list[ParsedRow] = []
        checks: list[Check] = []
        if "ARS" not in sections or not sections["ARS"]["cells"]:
            raise ParseError("No se encontraron movimientos en pesos")
        for cur, sec in sections.items():
            rows_cur, opening = [], None
            for c in sec["cells"]:
                saldo = parse_money(c["saldo"])
                if c["title"].lower().startswith("saldo inicial"):
                    opening = saldo; continue
                amt_caja, amt_cc = parse_money(c["caja"]), parse_money(c["cc"])
                amount = amt_caja if amt_caja is not None else amt_cc
                if amount is None or saldo is None or c["date"] is None:
                    sec["bad"] += 1; continue
                details = [mask(x) for x in c["details"]]
                cp = next((m.group(1) for x in details if (m := COUNTERPARTY.match(x))), None)
                rows_cur.append(ParsedRow(
                    date=_d(c["date"]), description_raw=" ".join([mask(c["title"])] + details).strip(),
                    amount=amount, currency=cur, external_id=c["comp"], counterparty=cp, balance_after=saldo))
            rows += rows_cur
            pre = "" if cur == "ARS" else f"{cur.lower()}_"
            prev, breaks = opening, 0
            for r in rows_cur:
                if prev is not None and abs(prev + r.amount - r.balance_after) > TOL:
                    breaks += 1
                prev = r.balance_after
            closing = sec["closing"]
            checks += [
                Check(f"{pre}opening_found", opening is not None or not rows_cur, "saldo inicial de la sección"),
                Check(f"{pre}running_balance", breaks == 0, f"{breaks} saltos de saldo"),
                Check(f"{pre}all_cells_parsed", sec["bad"] == 0, f"{sec['bad']} celdas ilegibles"),
                Check(f"{pre}closing_balance", closing is not None and (prev == closing if prev is not None else True),
                      "saldo final = 'Saldo total' declarado"),
            ]
        return ParsedStatement(
            parser_key=self.key, rows=rows, currencies=sorted({r.currency for r in rows}) or ["ARS"],
            period_start=p_start, period_end=p_end,
            declared_totals={f"closing_{k}": v["closing"] for k, v in sections.items()}, validation=checks,
        )
