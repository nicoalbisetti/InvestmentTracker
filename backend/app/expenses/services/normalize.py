import re
import unicodedata

PREFIXES = ("MERPAGO*", "MP*", "PAYU*AR*", "DLO*", "PVS*", "AMAZONMKTPLC*", "UBER* ", "ANT*")
_BRANCH_DASH = re.compile(r"[-\s]\d+$")
_BRANCH_GLUED = re.compile(r"(?<=[A-Z])\d+$")
_BRANCH_FL = re.compile(r"\sFL\s?\d+$")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize_merchant(raw: str) -> str:
    s = re.sub(r"\s+", " ", raw.upper()).strip()
    for p in PREFIXES:
        if s.startswith(p):
            s = s[len(p):].strip()
            break
    prev = None
    while prev != s:  # sucursales encadenadas: 'X-2071', 'RAIA1732', 'LOJAS RENNER FL 481'
        prev = s
        s = _BRANCH_FL.sub("", s)
        s = _BRANCH_DASH.sub("", s) if re.search(r"[A-Z]", s) else s
        s = _BRANCH_GLUED.sub("", s)
        s = s.strip()
    return s


def match_key(raw: str) -> str:
    """Clave de matching sin no-alfanuméricos: 'APPLE.COM/BILL' -> 'APPLECOMBILL'."""
    return re.sub(r"[^A-Z0-9]", "", strip_accents(raw).upper())
