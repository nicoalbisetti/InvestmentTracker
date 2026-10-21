from typing import Optional

from app.expenses.parsers.inter_account_csv import InterAccountCsv
from app.expenses.parsers.mercadopago_pdf import MercadoPagoPdf
from app.expenses.parsers.santander_ar_account_pdf import SantanderArAccountPdf
from app.expenses.parsers.xp_account_csv import XpAccountCsv
from app.expenses.parsers.xp_card_csv import XpCardCsv

PARSERS = [XpAccountCsv(), XpCardCsv(), InterAccountCsv(), MercadoPagoPdf(), SantanderArAccountPdf()]


def get_parser(key: str):
    for p in PARSERS:
        if p.key == key:
            return p
    raise KeyError(key)


def detect_parser(filename: str, head_bytes: bytes) -> Optional[object]:
    """Devuelve el único parser que reconoce el archivo (None si ninguno o si hay ambigüedad)."""
    hits = [p for p in PARSERS if p.detect(filename, head_bytes)]
    return hits[0] if len(hits) == 1 else None
