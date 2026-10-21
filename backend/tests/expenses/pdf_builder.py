"""Genera PDFs sintéticos mínimos (texto posicionado + filetes finos) sin dependencias externas."""
W, H = 446.0, 632.0


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(pages: list[dict]) -> bytes:
    """pages: [{"texts": [(x, top, texto)], "rules": [(x, top, ancho)], "boxes": [(x, top, ancho, alto)]}]"""
    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, pg in enumerate(pages):
        ops = []
        for x, top, text in pg.get("texts", []):
            ops.append(f"BT /F1 6.5 Tf {x:.2f} {H - top - 8:.2f} Td ({_esc(text)}) Tj ET")
        for x, top, w in pg.get("rules", []):
            ops.append(f"{x:.2f} {H - top:.2f} {w:.2f} 0.75 re f")
        for x, top, w, h in pg.get("boxes", []):  # rectángulos con alto (celdas de encabezado)
            ops.append(f"{x:.2f} {H - top - h:.2f} {w:.2f} {h:.2f} re f")
        stream = "\n".join(ops).encode("cp1252", "replace")
        page_no, content_no = 4 + 2 * i, 5 + 2 * i
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] /Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_no} 0 R >>".encode())
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
