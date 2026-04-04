"""
Router: /api/import/international
Handles preview and confirmation of XP International PDF imports.
"""
from __future__ import annotations

import json
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.instrument_code_mapping import InstrumentCodeMapping
from app.services.international_importer import (
    InternationalImportConfig,
    InternationalDiffItem,
    DividendDiffItem,
    apply_import_dividends,
    apply_import_positions,
    check_dividend_duplicates,
    compute_position_diffs,
    get_usd_brl_rate,
    load_preview,
    parse_xp_international_pdf,
    store_preview,
)

router = APIRouter(prefix="/api/import/international", tags=["import-international"])


@router.post("/debug-pdf")
async def debug_pdf(file: UploadFile = File(...)):
    """Return raw pdfplumber extraction for debugging parser issues."""
    import io
    import pdfplumber

    pdf_bytes = await file.read()
    result = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            result.append({
                "page": i + 1,
                "text_snippet": text[:500],
                "num_tables": len(tables),
                "tables": [
                    {
                        "num_rows": len(t),
                        "rows": t[:10],  # first 10 rows only
                    }
                    for t in tables
                ],
            })
    return result


# ─── Endpoint 1: Preview ──────────────────────────────────────────────────────

@router.post("/preview")
async def preview_import(
    file: UploadFile = File(...),
    period_date: str = Form(...),
    config: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Parse a PDF, compute diffs for positions and dividends, and return a preview.
    Does NOT write anything to the database.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF (.pdf)")

    try:
        cfg = InternationalImportConfig(**json.loads(config))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Config inválida: {e}")

    pdf_bytes = await file.read()

    # Parse the PDF
    try:
        report = parse_xp_international_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error al parsear el PDF: {e}")

    # Determine period_date (first of month)
    try:
        pd_date = date.fromisoformat(period_date)
        pd_date = pd_date.replace(day=1)
    except ValueError:
        raise HTTPException(status_code=422, detail="period_date debe ser YYYY-MM-DD")

    # Suggest USD/BRL rate from yfinance
    ref_date = report.period_end or pd_date
    usd_brl_suggested = get_usd_brl_rate(ref_date)

    # Use config rate if provided and valid, else use suggested
    effective_rate = cfg.usd_brl_rate if cfg.usd_brl_rate > 0 else (usd_brl_suggested or 0.0)

    # Compute diffs
    position_diffs = compute_position_diffs(report.positions, effective_rate, pd_date, db)
    dividend_diffs = check_dividend_duplicates(report.dividends, effective_rate, db)

    # Store in cache
    token = store_preview(report, position_diffs, dividend_diffs, usd_brl_suggested)

    # Build summary
    new_count = sum(1 for d in position_diffs if d.diff_status == "NEW")
    updated_count = sum(1 for d in position_diffs if d.diff_status == "UPDATED")
    unchanged_count = sum(1 for d in position_diffs if d.diff_status == "UNCHANGED")
    new_instr_count = sum(1 for d in position_diffs if d.match_status == "NEW")
    total_usd = sum(d.posicao_usd for d in position_diffs)
    total_brl = sum(d.posicao_brl for d in position_diffs)

    div_new = sum(1 for d in dividend_diffs if d.dup_status == "NEW")
    div_dup = sum(1 for d in dividend_diffs if d.dup_status == "DUPLICATE")
    div_total_usd = sum(d.valor_liquido_usd for d in dividend_diffs if d.dup_status == "NEW")
    div_total_brl = sum(d.valor_liquido_brl for d in dividend_diffs if d.dup_status == "NEW")

    return {
        "file_token": token,
        "period_date": pd_date.isoformat(),
        "period_end": report.period_end.isoformat() if report.period_end else None,
        "account_number": report.account_number,
        "usd_brl_rate_suggested": usd_brl_suggested,
        "positions_summary": {
            "total_in_pdf": len(position_diffs),
            "total_usd": round(total_usd, 2),
            "total_brl": round(total_brl, 2),
            "new_instruments": new_instr_count,
            "updated": updated_count,
            "unchanged": unchanged_count,
            "new": new_count,
        },
        "dividends_summary": {
            "total_in_pdf": len(dividend_diffs),
            "total_usd_neto": round(div_total_usd, 2),
            "total_brl_neto": round(div_total_brl, 2),
            "new": div_new,
            "duplicates": div_dup,
        },
        "position_diffs": [d.model_dump() for d in position_diffs],
        "dividend_diffs": [d.model_dump() for d in dividend_diffs],
        "parse_warnings": report.parse_warnings,
    }


# ─── Endpoint 2: Confirm ──────────────────────────────────────────────────────

class ManualMapping(BaseModel):
    key: str
    instrument_id: int


class ConfirmRequest(BaseModel):
    file_token: str
    config: InternationalImportConfig
    skip_cusips: List[str] = []
    skip_dividend_indices: List[int] = []
    manual_mappings: List[ManualMapping] = []


@router.post("/confirm")
def confirm_import(payload: ConfirmRequest, db: Session = Depends(get_db)):
    """Apply the previously previewed import to the database."""
    entry = load_preview(payload.file_token)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Token expirado o inválido. Por favor realizá el preview nuevamente.",
        )

    position_diffs: List[InternationalDiffItem] = entry["position_diffs"]
    dividend_diffs: List[DividendDiffItem] = entry["dividend_diffs"]

    # Recompute BRL amounts with the final usd_brl_rate from config
    final_rate = payload.config.usd_brl_rate
    for diff in position_diffs:
        diff.posicao_brl = diff.posicao_usd * final_rate
    for div in dividend_diffs:
        div.valor_liquido_brl = div.valor_liquido_usd * final_rate

    manual_map = {m.key: m.instrument_id for m in payload.manual_mappings}

    positions_result = apply_import_positions(
        position_diffs, payload.config, payload.skip_cusips, manual_map, db
    )
    dividends_result = apply_import_dividends(
        dividend_diffs, payload.config, payload.skip_dividend_indices, manual_map, db
    )

    return {
        "success": True,
        "positions_imported": positions_result,
        "dividends_imported": dividends_result,
        "warnings": [],
    }


# ─── Endpoint 3: Manual Instrument Mapping ────────────────────────────────────

class MapInstrumentRequest(BaseModel):
    key: str
    instrument_id: int


@router.post("/map-instrument")
def map_instrument(payload: MapInstrumentRequest, db: Session = Depends(get_db)):
    """Persist a manual mapping from a CUSIP or ticker to an instrument_id."""
    existing = db.query(InstrumentCodeMapping).filter(
        InstrumentCodeMapping.codigo_excel == payload.key
    ).first()
    if existing:
        existing.instrument_id = payload.instrument_id
    else:
        db.add(InstrumentCodeMapping(
            codigo_excel=payload.key,
            instrument_id=payload.instrument_id,
        ))
    db.commit()
    return {"ok": True, "key": payload.key, "instrument_id": payload.instrument_id}
