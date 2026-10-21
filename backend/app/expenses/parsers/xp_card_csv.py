"""Fatura de tarjeta XP (Brasil). CSV ';' con BOM, columnas Data;Estabelecimento;Portador;Valor;Parcela."""
import re
from decimal import Decimal

from app.expenses.parsers._csv import dict_rows, parse_date, read_text
from app.expenses.parsers.base import Check, NeedsDueDate, ParsedRow, ParsedStatement, ParseError
from app.expenses.parsers.numbers import parse_money

HEADER = "Data;Estabelecimento;Portador;Valor;Parcela"
FILENAME_RE = re.compile(r"Fatura(\d{4})-(\d{2})-(\d{2})", re.I)
PAYMENT_RE = re.compile(r"^(Pagamentos? V[aá]lidos? Normais|Pagamento de fatura)\s*$", re.I)
INSTALLMENT_RE = re.compile(r"^\s*(\d+)\s+de\s+(\d+)\s*$")


class XpCardCsv:
    key = "xp_card_csv"

    def detect(self, filename: str, head_bytes: bytes) -> bool:
        return head_bytes.decode("utf-8-sig", errors="ignore").lstrip().startswith(HEADER)

    def parse(self, path, due_date=None, **_) -> ParsedStatement:
        if due_date is None:
            m = FILENAME_RE.search(str(path).replace("\\", "/").rsplit("/", 1)[-1])
            if not m:
                raise NeedsDueDate("No se pudo inferir el vencimiento del nombre del archivo")
            from datetime import date as _d
            due_date = _d(int(m.group(1)), int(m.group(2)), int(m.group(3)))

        rows: list[ParsedRow] = []
        for r in dict_rows(read_text(path)):
            desc = (r.get("Estabelecimento") or "").strip()
            amount = parse_money(r.get("Valor"))
            if not desc and amount is None:
                continue
            if amount is None:
                raise ParseError(f"Valor inválido en {desc!r}")
            n = total = None
            m = INSTALLMENT_RE.match(r.get("Parcela") or "")
            if m and int(m.group(2)) > 1:
                n, total = int(m.group(1)), int(m.group(2))
            hint = None
            if amount < 0:  # crédito en la fatura
                hint = "card_payment" if PAYMENT_RE.match(desc) else "refund"
            amount = -amount  # convención del módulo: consumo negativo, pago/devolución positivo
            rows.append(ParsedRow(
                date=due_date, purchase_date=parse_date(r["Data"]), description_raw=desc,
                amount=amount, currency="BRL", installment_number=n, installment_total=total,
                kind_hint=hint,
            ))

        # Totales en el signo de la fatura (lo que se debe es positivo).
        total_statement = -sum((x.amount for x in rows if x.kind_hint != "card_payment"), Decimal("0"))
        payments = -sum((x.amount for x in rows if x.kind_hint == "card_payment"), Decimal("0"))
        checks = [
            Check("rows_found", bool(rows), f"{len(rows)} filas"),
            Check("single_card_payment_type", sum(1 for x in rows if x.kind_hint == "card_payment") <= 1,
                  "como máximo una línea de pago de la fatura anterior"),
        ]
        return ParsedStatement(
            parser_key=self.key, rows=rows, currencies=["BRL"],
            period_start=min((x.purchase_date for x in rows), default=None), period_end=due_date,
            statement_due_date=due_date, statement_period=due_date.strftime("%Y-%m"),
            declared_totals={"statement_total": total_statement, "previous_payment": payments},
            validation=checks,
        )
