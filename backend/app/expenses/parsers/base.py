from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional, Protocol


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""  # nunca incluir identificadores (cuentas, documentos)


@dataclass
class ParsedRow:
    date: date                              # imputación (movimiento / vencimiento en tarjetas)
    description_raw: str
    amount: Decimal                         # con signo; negativo = sale dinero
    currency: str
    purchase_date: Optional[date] = None
    counterparty: Optional[str] = None
    external_id: Optional[str] = None
    installment_number: Optional[int] = None
    installment_total: Optional[int] = None
    balance_after: Optional[Decimal] = None
    time: Optional[str] = None              # HH:MM:SS si el formato lo trae (desempate / hash)
    kind_hint: Optional[str] = None         # card_payment | refund (sólo cuando el formato lo determina)


@dataclass
class ParsedStatement:
    parser_key: str
    rows: list[ParsedRow]
    currencies: list[str]
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    statement_due_date: Optional[date] = None
    statement_period: Optional[str] = None
    declared_totals: dict = field(default_factory=dict)
    validation: list[Check] = field(default_factory=list)
    account_hint: Optional[str] = None   # p. ej. 'VISA' / 'AMEX': ayuda a elegir la cuenta

    @property
    def checks_ok(self) -> bool:
        return all(c.ok for c in self.validation)


class ParseError(Exception):
    pass


class NeedsDueDate(ParseError):
    """La fecha de vencimiento no se pudo inferir: pedirla en el import."""


class StatementParser(Protocol):
    key: str

    def detect(self, filename: str, head_bytes: bytes) -> bool: ...

    def parse(self, path, **opts) -> ParsedStatement: ...
