"""Cuenta corriente Inter (Brasil). Preámbulo + encabezado 'Data Lançamento;Descrição;Valor;Saldo'."""
import re
from decimal import Decimal

from app.expenses.parsers._csv import dict_rows, parse_date, read_text
from app.expenses.parsers.base import Check, ParsedRow, ParsedStatement, ParseError
from app.expenses.parsers.numbers import parse_money

HEADER_PREFIX = "Data Lançamento;"
PERIOD_RE = re.compile(r"Per[ií]odo\s*;\s*(\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})")
CP_RE = re.compile(r'Cp\s*:\s*\d+-(.*?)"?\s*$')
OWN_BANK_RE = re.compile(r"\b0*\d{3,5}\s+\d+\s+(BANCO INTER S\.?\s?A\.?)", re.I)


def _counterparty(desc: str):
    m = CP_RE.search(desc)
    if m:
        return m.group(1).strip().strip('"') or None
    m = OWN_BANK_RE.search(desc)
    return m.group(1).strip() if m else None


class InterAccountCsv:
    key = "inter_account_csv"

    def detect(self, filename: str, head_bytes: bytes) -> bool:
        head = head_bytes.decode("utf-8-sig", errors="ignore")
        return "Extrato Conta Corrente" in head and HEADER_PREFIX in head

    def parse(self, path, **_) -> ParsedStatement:
        lines = read_text(path).splitlines()
        idx = next((i for i, l in enumerate(lines) if l.startswith(HEADER_PREFIX)), None)
        if idx is None:
            raise ParseError("No se encontró el encabezado de movimientos")
        period = PERIOD_RE.search("\n".join(lines[:idx]))
        p_start = parse_date(period.group(1)) if period else None
        p_end = parse_date(period.group(2)) if period else None

        rows: list[ParsedRow] = []
        for r in dict_rows("\n".join(lines[idx:])):
            if not (r.get("Data Lançamento") or "").strip():
                continue
            desc = (r["Descrição"] or "").strip()
            amount, balance = parse_money(r["Valor"]), parse_money(r["Saldo"])
            if amount is None or balance is None:
                raise ParseError("Importe o saldo inválido")
            rows.append(ParsedRow(
                date=parse_date(r["Data Lançamento"]), description_raw=desc, amount=amount,
                currency="BRL", counterparty=_counterparty(desc), balance_after=balance,
            ))

        # El archivo viene en orden cronológico; no se asume: se valida en el orden dado.
        breaks = sum(
            1 for a, b in zip(rows, rows[1:]) if abs(a.balance_after + b.amount - b.balance_after) > Decimal("0.005")
        )
        checks = [
            Check("rows_found", bool(rows), f"{len(rows)} filas"),
            Check("running_balance", breaks == 0, f"{breaks} saltos de saldo"),
        ]
        if p_start and rows:
            inside = all(p_start <= x.date <= p_end for x in rows)
            checks.append(Check("within_declared_period", inside, "movimientos dentro del período declarado"))
        return ParsedStatement(
            parser_key=self.key, rows=rows, currencies=["BRL"],
            period_start=p_start or (rows[0].date if rows else None),
            period_end=p_end or (rows[-1].date if rows else None),
            declared_totals={"closing_balance": rows[-1].balance_after if rows else None},
            validation=checks,
        )
