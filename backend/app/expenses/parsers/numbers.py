"""Parseo de importes con formato BR/AR ('.' miles, ',' decimal) y sus variantes de extractos.

Variantes soportadas: 'R$ 1.234,56', '-R$ 1.234,56', '-$ 26.555,51', '$ -565.200,00',
'1672.047,98-' (signo al final), '1672047,98' (sin miles), '$ 103.091 80' (decimales con espacio).
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

_SPACE_DEC = re.compile(r"(\d)\s(\d{2})$")


def parse_money(val) -> Optional[Decimal]:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    s = str(val).strip()
    if not s or s in ("-", "nan", "None"):
        return None
    negative = "-" in s
    s = s.replace("R$", "").replace("U$S", "").replace("$", "").replace("-", "").strip()
    s = _SPACE_DEC.sub(r"\1,\2", s)
    s = s.replace(" ", "")
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return -d if negative else d


# Alias con el nombre de cada país: mismo formato numérico.
parse_br_number = parse_money
parse_ar_number = parse_money
