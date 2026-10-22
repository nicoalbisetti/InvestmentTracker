"""Resumen de tarjeta Santander Argentina (VISA y AMEX, mismo layout, PDF).

Una línea de texto = un movimiento. Cada dato se toma por su columna (x): año/mes/día, comprobante,
referencia, cuota, importe en pesos e importe en dólares. Año y mes se arrastran entre líneas y páginas.

Convención del módulo: consumo negativo, crédito (pago/devolución) positivo. Los consumos e impuestos
se imputan al vencimiento (`date`) y conservan su fecha original en `purchase_date`; los pagos llevan
su fecha real (es la fecha que concilia con el débito en la cuenta).
"""
import io
import re
from datetime import date
from decimal import Decimal
from typing import Optional

import pdfplumber

from app.expenses.parsers._pdf import first_page_text, is_pdf, read_bytes
from app.expenses.parsers.base import Check, ParsedRow, ParsedStatement, ParseError
from app.expenses.parsers.mercadopago_pdf import _lines
from app.expenses.parsers.numbers import parse_money
from app.expenses.parsers.santander_ar_account_pdf import mask

MONEY_TOKEN = re.compile(r"^-?\d[\d.]*,\d{2}-?$")
CUOTA = re.compile(r"^C\.(\d{2})/(\d{2})$")
TC_TOKEN = re.compile(r"^TC[\d.,]+$")
MONTHS = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "sep": 9,
          "oct": 10, "nov": 11, "dic": 12}
HEADER = re.compile(r"CIERRE\s+(\d{2})\s+([A-Za-z]{3})\s+(\d{2})\s*VENCIMIENTO\s+(\d{2})\s+([A-Za-z]{3})\s+(\d{2})")
DEBIT = re.compile(r"DEBITAREMOS DE SU C\.C\.\S*\s+LA SUMA DE\s+\$\s*([\d.,]+)(?:\s*\+\s*U\$S\s*([\d.,]+))?")
X_YEAR, X_DAY_LO, X_DAY_HI, X_REF, X_AMT_ARS, X_AMT_USD = 34, 60, 88, 130, 395, 495
TOL_ARS, TOL_USD = Decimal("1.00"), Decimal("0.011")


def _month(token: str) -> Optional[int]:
    return MONTHS.get(token[:3].lower())


def _signed(tok: str) -> Decimal:
    """'1.234,56-' -> -1234.56 (crédito); '1.234,56' -> 1234.56 (cargo), en signo de resumen."""
    v = parse_money(tok.rstrip("-"))
    return -v if tok.endswith("-") else v


def _money_tokens(ws, lo, hi):
    return [w for w in ws if lo <= w["x0"] < hi and MONEY_TOKEN.match(w["text"])]


def parse_lines(pages_lines, due: date):
    """pages_lines: [[(top, [words])]] de la zona de movimientos. Devuelve (items, totals, saldo_ant)."""
    year = month = None
    items, totals, prev_balance = [], [], {"ARS": Decimal("0"), "USD": Decimal("0")}
    n_consumption_total_seen = 0
    for lines in pages_lines:
        for _, ws in lines:
            text = " ".join(w["text"] for w in ws)
            if "Total" in text and "Consumos" in text:
                a, u = _money_tokens(ws, X_AMT_ARS, X_AMT_USD), _money_tokens(ws, X_AMT_USD, 1e9)
                totals.append({"ARS": parse_money(a[-1]["text"]) if a else None,
                               "USD": parse_money(u[0]["text"]) if u else None, "after_item": len(items)})
                n_consumption_total_seen += 1
                continue
            if "SALDO" in text and "ANTERIOR" in text:
                a, u = _money_tokens(ws, X_AMT_ARS, X_AMT_USD), _money_tokens(ws, X_AMT_USD, 1e9)
                prev_balance = {"ARS": parse_money(a[-1]["text"]) if a else Decimal("0"),
                                "USD": parse_money(u[0]["text"]) if u else Decimal("0")}
                continue
            day = next((w for w in ws if X_DAY_LO <= w["x0"] < X_DAY_HI and re.match(r"^\d{2}$", w["text"])), None)
            if day is None:
                continue
            yr = next((w for w in ws if w["x0"] < X_YEAR and re.match(r"^\d{2}$", w["text"])), None)
            mo = next((w for w in ws if X_YEAR <= w["x0"] < X_DAY_LO and re.match(r"^[A-Za-zÁ-ú]+\.?$", w["text"])), None)
            if yr:
                year = 2000 + int(yr["text"])
            if mo and _month(mo["text"]):
                month = _month(mo["text"])
            if year is None or month is None:
                raise ParseError("Línea con fecha incompleta")
            when = date(year, month, int(day["text"]))
            body = [w for w in ws if w["x0"] >= X_REF - 2]
            ars = _money_tokens(ws, X_AMT_ARS, X_AMT_USD)
            usd = _money_tokens(ws, X_AMT_USD, 1e9)
            cash = _money_tokens(body, X_REF, X_AMT_ARS)  # importe en la zona de referencia (pago con TC)
            ref = [w["text"] for w in body if X_REF <= w["x0"] < X_AMT_ARS and not MONEY_TOKEN.match(w["text"])
                   and not TC_TOKEN.match(w["text"]) and w["text"] != "$" and not CUOTA.match(w["text"])]
            ref = [t for t in ref if t != "*"]
            desc = " ".join(ref).strip()
            cuota = next((CUOTA.match(w["text"]) for w in body if CUOTA.match(w["text"])), None)
            items.append({
                "when": when, "desc": desc, "cuota": (int(cuota.group(1)), int(cuota.group(2))) if cuota else None,
                "ars": _signed(ars[-1]["text"]) if ars else None, "usd": _signed(usd[0]["text"]) if usd else None,
                "cash": parse_money(cash[0]["text"]) if cash else None, "tc": next(
                    (w["text"] for w in body if TC_TOKEN.match(w["text"])), None),
                "flag": next((w["text"] for w in ws if 110 <= w["x0"] < X_REF and len(w["text"]) == 1), None),
            })
    return items, totals, prev_balance


class SantanderArCardPdf:
    key = "santander_ar_card_pdf"

    def detect(self, filename: str, head_bytes: bytes) -> bool:
        if not is_pdf(head_bytes):
            return False
        t = first_page_text(head_bytes)
        # en AMEX el título sale con letras separadas ('R E S U M E N ...'): se compara sin espacios
        compact = re.sub(r"\s+", "", t).upper()
        return bool(HEADER.search(t)) and "RESUMENDECUENTA" in compact and "SANTANDER" in compact

    def parse(self, path, **_) -> ParsedStatement:
        data = read_bytes(path)
        pages_lines, full_text, brand = [], "", None
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                full_text += text + "\n"
                if i == 0:
                    brand = "AMEX" if re.search(r"AMERICAN EXPRESS|AMEX", text) else "VISA" if "VISA" in text else None
                lines = _lines(page.extract_words(), tol=2.5)
                head = next((t for t, ws in lines if {"Fecha", "Comprobante", "Referencia"} <= {w["text"] for w in ws}), None)
                if head is None:
                    continue
                end = next((t for t, ws in lines if t > head and "SALDO" in [w["text"] for w in ws]
                            and "ACTUAL" in [w["text"] for w in ws]), page.height)
                pages_lines.append([(t, ws) for t, ws in lines if head < t < end and not all(set(w["text"]) <= {"_"} for w in ws)])

        h = HEADER.search(full_text)
        if not h:
            raise ParseError("No se encontró cierre/vencimiento")
        close = date(2000 + int(h.group(3)), MONTHS[h.group(2).lower()], int(h.group(1)))
        due = date(2000 + int(h.group(6)), MONTHS[h.group(5).lower()], int(h.group(4)))

        items, totals, prev = parse_lines(pages_lines, due)
        rows: list[ParsedRow] = []
        consumption = {"ARS": Decimal("0"), "USD": Decimal("0")}
        printed = {"ARS": Decimal("0"), "USD": Decimal("0")}
        first_total_at = totals[0]["after_item"] if totals else len(items)
        for idx, it in enumerate(items):
            desc = mask(it["desc"])
            is_payment = desc.startswith("SU PAGO")
            is_debt_transfer = desc.startswith("TRANSFERENCIA DEUDA")
            desc = re.sub(r"\s+(USD|EUR|BRL)\b$", "", desc).strip()
            for cur, key in (("ARS", "ars"), ("USD", "usd")):
                v = it[key]
                if v is None:
                    continue
                printed[cur] += v
                if idx < first_total_at and not is_payment and not is_debt_transfer:
                    consumption[cur] += v
            targets = []
            if is_payment and it["cash"] is not None:
                targets.append(("ARS", it["cash"]))        # pesos efectivamente debitados (incluye USD x TC)
            else:
                targets += [(c, -it[k]) for c, k in (("ARS", "ars"), ("USD", "usd")) if it[k] is not None]
            for cur, amount in targets:
                if is_payment:
                    row_date, purchase, hint = it["when"], None, "card_payment"
                    text = f"{desc} {it['tc']}" if it["tc"] else desc
                elif is_debt_transfer:
                    row_date, purchase, hint, text = due, it["when"], "fx_conversion", desc
                else:
                    row_date, purchase, hint, text = due, it["when"], ("refund" if amount > 0 else None), desc
                n, total = it["cuota"] if it["cuota"] and it["cuota"][1] > 1 else (None, None)
                rows.append(ParsedRow(
                    date=row_date, purchase_date=purchase, description_raw=text, amount=amount, currency=cur,
                    installment_number=n, installment_total=total, kind_hint=hint))

        m = DEBIT.search(full_text)
        declared = {}
        if m:
            declared = {"ARS": parse_money(m.group(1)), "USD": parse_money(m.group(2)) if m.group(2) else Decimal("0")}
        checks = [
            Check("rows_found", bool(rows), f"{len(rows)} filas"),
            Check("debit_line_found", bool(declared), "línea DEBITAREMOS presente"),
        ]
        if declared:
            exp_ars, exp_usd = prev["ARS"] + printed["ARS"], prev["USD"] + printed["USD"]
            checks += [
                Check("debit_ars", abs(exp_ars - declared["ARS"]) <= TOL_ARS,
                      f"saldo anterior + movimientos = DEBITAREMOS (dif {exp_ars - declared['ARS']:.2f})"),
                Check("debit_usd", abs(exp_usd - declared["USD"]) <= TOL_USD,
                      f"dif USD {exp_usd - declared['USD']:.2f}"),
            ]
        if totals:
            t_ars = sum((t["ARS"] or Decimal("0")) for t in totals)
            t_usd = sum((t["USD"] or Decimal("0")) for t in totals)
            checks += [Check("total_consumos_ars", abs(consumption["ARS"] - t_ars) <= TOL_ARS, "Σ consumos = 'Total Consumos'"),
                       Check("total_consumos_usd", abs(consumption["USD"] - t_usd) <= TOL_USD, "Σ consumos USD = 'Total Consumos'")]
        else:
            checks.append(Check("total_consumos_found", False, "no se encontró 'Total Consumos'"))

        return ParsedStatement(
            parser_key=self.key, rows=rows, currencies=sorted({r.currency for r in rows}) or ["ARS"],
            period_start=min((r.purchase_date for r in rows if r.purchase_date), default=None), period_end=due,
            statement_due_date=due, statement_period=due.strftime("%Y-%m"),
            declared_totals={"ARS": declared.get("ARS"), "USD": declared.get("USD"), "close_date": close.isoformat()},
            validation=checks, account_hint=brand,
        )
