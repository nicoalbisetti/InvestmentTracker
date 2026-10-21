import io
from functools import lru_cache

import pdfplumber


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


@lru_cache(maxsize=4)
def first_page_text(data: bytes) -> str:
    """Texto de la primera página (para detectar el formato por contenido, no por nombre)."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return pdf.pages[0].extract_text() or ""
    except Exception:  # noqa: BLE001  (PDF corrupto o protegido: simplemente no es de este formato)
        return ""


def read_bytes(path) -> bytes:
    with open(path, "rb") as f:
        return f.read()
