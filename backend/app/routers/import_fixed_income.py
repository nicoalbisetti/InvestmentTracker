import json
from datetime import date, datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.instrument import Instrument
from app.models.instrument_code_mapping import InstrumentCodeMapping
from app.schemas.fixed_income_import import (
    ImportConfig, ConfirmRequest, MapInstrumentRequest,
    PreviewResponse, PreviewSummary, ImportResult,
)
from app.services.fixed_income_importer import (
    parse_excel, compute_diff, apply_import,
    store_preview, load_preview, update_diff_item, _make_skip_key,
    _extract_keywords, auto_match_score, ParsedInstrument,
)

router = APIRouter(prefix="/api/import/fixed-income", tags=["import-fixed-income"])


@router.post("/preview", response_model=PreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    period_date: str = Form(...),
    config: str = Form("{}"),
    db: Session = Depends(get_db),
):
    """
    Step 1: Parse the Excel file and compute a diff preview.
    Returns a file_token valid for 30 minutes to use in /confirm.
    """
    # Parse config JSON
    try:
        config_dict = json.loads(config)
        import_config = ImportConfig(**config_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid config: {e}")

    # Parse period_date
    try:
        pd_obj = date.fromisoformat(period_date)
        # Normalize to first of month
        pd_obj = pd_obj.replace(day=1)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid period_date: {period_date}")

    # Validate file
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=422, detail="File must be an Excel file (.xlsx or .xls)")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    # Parse Excel
    try:
        parsed, parse_warnings = parse_excel(file_bytes, import_config)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error parsing Excel: {e}")

    if not parsed:
        raise HTTPException(
            status_code=422,
            detail="No instruments found. Verify the file contains 'Posição - Renda Fixa' or 'Posição - Tesouro Direto' sheets."
        )

    # Check if period already has data
    from app.models.monthly_position import MonthlyPosition
    existing_count = db.query(MonthlyPosition).filter(MonthlyPosition.date == pd_obj).count()
    if existing_count > 0:
        parse_warnings.append(f"Período {pd_obj.strftime('%B %Y')} ya tiene {existing_count} posiciones registradas — se actualizarán")

    # Compute diff
    try:
        diff = compute_diff(parsed, pd_obj, import_config, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing diff: {e}")

    # Build summary
    new_count = sum(1 for d in diff if d.status == "NEW")
    updated_count = sum(1 for d in diff if d.status == "UPDATED")
    unchanged_count = sum(1 for d in diff if d.status == "UNCHANGED")
    disappeared_count = sum(1 for d in diff if d.status == "DISAPPEARED")
    no_price_count = sum(1 for d in diff if d.valor_actual_brl is None and d.status != "DISAPPEARED")

    summary = PreviewSummary(
        total_in_file=len(parsed),
        new_instruments=new_count,
        updated_positions=updated_count,
        unchanged=unchanged_count,
        disappeared=disappeared_count,
        parse_errors=0,
        no_price_available=no_price_count,
    )

    # Store in token cache
    token, expires = store_preview(import_config, diff, parsed)

    return PreviewResponse(
        file_token=token,
        period_date=pd_obj,
        summary=summary,
        differences=diff,
        parse_warnings=parse_warnings,
        expires_at=expires,
    )


@router.post("/confirm", response_model=ImportResult)
def confirm_import(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Step 2: Apply the confirmed import using the preview token.
    skip_codes are "codigo::custodian_override" strings for items to exclude.
    """
    entry = load_preview(body.file_token)
    if entry is None:
        raise HTTPException(
            status_code=410,
            detail="El token de importación expiró (30 min) o no es válido. Vuelva a cargar el archivo."
        )

    diff = entry["diff"]
    parsed = entry["parsed"]
    config = entry["config"]

    try:
        pd_obj = date.fromisoformat(body.period_date).replace(day=1)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid period_date: {body.period_date}")

    result = apply_import(diff, parsed, pd_obj, config, body.skip_codes, db)
    return result


@router.get("/suggestions")
def get_suggestions(
    file_token: str,
    codigo: str,
    db: Session = Depends(get_db),
):
    """
    Return scored list of existing renta_fija instruments that might match
    the given codigo from the current preview session.
    """
    entry = load_preview(file_token)
    if entry is None:
        raise HTTPException(status_code=410, detail="Token expirado o inválido")

    # Find the DiffItem for this codigo
    diff_item = next((d for d in entry["diff"] if d.codigo == codigo), None)
    if diff_item is None:
        raise HTTPException(status_code=404, detail=f"Codigo {codigo} no encontrado en la sesión")

    # Find corresponding ParsedInstrument
    parsed_item = next((p for p in entry["parsed"] if p.codigo == codigo), None)

    # Get ALL renta_fija instruments (including cerrado) so the user can map to any
    candidates = db.query(Instrument).order_by(Instrument.name).all()

    results = []
    for inst in candidates:
        score = auto_match_score(parsed_item, inst) if parsed_item else 0
        results.append({
            "id": inst.id,
            "name": inst.name,
            "custodian": inst.custodian,
            "maturity_date": inst.maturity_date.isoformat() if inst.maturity_date else None,
            "score": score,
        })

    # Sort by score desc, then name
    results.sort(key=lambda x: (-x["score"], x["name"]))
    return {"suggestions": results}


@router.post("/map-instrument")
def map_instrument(
    body: MapInstrumentRequest,
    db: Session = Depends(get_db),
):
    """
    Save a persistent mapping from an Excel codigo to an existing instrument_id.
    Also updates any cached DiffItems with that codigo.
    """
    from app.models.instrument import Instrument
    inst = db.query(Instrument).filter(Instrument.id == body.instrument_id).first()
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Instrument {body.instrument_id} not found")

    # Upsert mapping
    existing = db.query(InstrumentCodeMapping).filter(
        InstrumentCodeMapping.codigo_excel == body.codigo_excel
    ).first()
    if existing:
        existing.instrument_id = body.instrument_id
    else:
        db.add(InstrumentCodeMapping(
            codigo_excel=body.codigo_excel,
            instrument_id=body.instrument_id,
        ))
    db.commit()

    # Update ticker on instrument if not set
    if not inst.ticker:
        inst.ticker = body.codigo_excel
        db.commit()

    # Update in-memory diff cache so the item changes NEW → UPDATED in current session
    if body.file_token:
        update_diff_item(body.file_token, body.codigo_excel, body.custodian_override, body.instrument_id)

    return {"ok": True, "codigo_excel": body.codigo_excel, "instrument_id": body.instrument_id,
            "instrument_name": inst.name}
