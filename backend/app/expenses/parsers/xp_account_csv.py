"""Cuenta XP (Brasil). CSV ';' con BOM: Data;Hora;Descricao;Valor;Saldo, orden descendente.

Invertir el archivo no alcanza: dentro de un mismo segundo el orden viene ascendente. El orden
cronológico se reconstruye con la cadena de saldos (saldo previo + valor = saldo).
"""
from decimal import Decimal
from itertools import groupby

from app.expenses.parsers._csv import dict_rows, parse_date, read_text
from app.expenses.parsers.base import Check, ParsedRow, ParsedStatement, ParseError
from app.expenses.parsers.numbers import parse_money

HEADER = "Data;Hora;Descricao;Valor;Saldo"
TOL = Decimal("0.005")


def _chain(prev, group):
    """Ordena `group` de modo que prev -> ... encadene por saldo. None si no hay orden válido."""
    remaining = list(group)
    ordered = []
    cur = prev
    while remaining:
        pick = next((r for r in remaining if abs(cur + r.amount - r.balance_after) <= TOL), None)
        if pick is None:
            return None
        ordered.append(pick)
        remaining.remove(pick)
        cur = pick.balance_after
    return ordered


def order_chronologically(rows: list[ParsedRow]):
    """rows en cualquier orden. Devuelve (rows_ordenadas, saltos_de_saldo)."""
    keyf = lambda r: (r.date, r.time or "")
    # el archivo es descendente: dentro de un empate conserva el orden del archivo invertido
    base = sorted(reversed(rows), key=keyf)
    out: list[ParsedRow] = []
    prev = None
    breaks = 0
    for _, g in groupby(base, key=keyf):
        group = list(g)
        if len(group) == 1:
            ordered = group
        elif prev is None:
            ordered = next(
                (o for start in group
                 if (o := _chain(start.balance_after - start.amount, group)) is not None), None)
        else:
            ordered = _chain(prev, group)
        if ordered is None:
            ordered = group
        for r in ordered:
            if prev is not None and abs(prev + r.amount - r.balance_after) > TOL:
                breaks += 1
            prev = r.balance_after
            out.append(r)
    return out, breaks


class XpAccountCsv:
    key = "xp_account_csv"

    def detect(self, filename: str, head_bytes: bytes) -> bool:
        return head_bytes.decode("utf-8-sig", errors="ignore").lstrip().startswith(HEADER)

    def parse(self, path, **_) -> ParsedStatement:
        rows: list[ParsedRow] = []
        for r in dict_rows(read_text(path)):
            if not (r.get("Data") or "").strip():
                continue
            amount, balance = parse_money(r["Valor"]), parse_money(r["Saldo"])
            if amount is None or balance is None:
                raise ParseError("Importe o saldo inválido")
            rows.append(ParsedRow(
                date=parse_date(r["Data"]), time=(r["Hora"] or "").strip() or None,
                description_raw=(r["Descricao"] or "").strip(), amount=amount, currency="BRL",
                balance_after=balance,
            ))
        rows, breaks = order_chronologically(rows)
        checks = [
            Check("rows_found", bool(rows), f"{len(rows)} filas"),
            Check("running_balance", breaks == 0, f"{breaks} saltos de saldo"),
        ]
        return ParsedStatement(
            parser_key=self.key, rows=rows, currencies=["BRL"],
            period_start=rows[0].date if rows else None, period_end=rows[-1].date if rows else None,
            declared_totals={
                "opening_balance": (rows[0].balance_after - rows[0].amount) if rows else None,
                "closing_balance": rows[-1].balance_after if rows else None,
            },
            validation=checks,
        )
