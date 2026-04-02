from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.provento_item import ProvéntoItem, ProventoImportBatch
from app.services.proventos_importer import (
    parse_excel, compute_diff, apply_import,
    store_preview, load_preview, update_diff_item_mapping,
)

router = APIRouter(prefix="/api/import/proventos", tags=["import-proventos"])


# ─── Request/Response schemas ──────────────────────────────────────────────────

class ManualMapping(BaseModel):
    index: int
    instrument_id: int


class ConfirmRequest(BaseModel):
    file_token: str
    period_label: str = ""
    force_duplicates: bool = False
    skip_indices: List[int] = []
    manual_mappings: List[ManualMapping] = []


class MapInstrumentRequest(BaseModel):
    file_token: str
    index: int
    instrument_id: int


# ─── Serializer helpers ────────────────────────────────────────────────────────

def _serialize_diff_item(item) -> dict:
    p = item.parsed
    return {
        "index": item.index,
        "status": item.status,
        "produto_raw": p.produto_raw,
        "ticker": p.ticker,
        "nombre_busqueda": p.nombre_busqueda,
        "tipo_evento_raw": p.tipo_evento_raw,
        "custodian": p.custodian,
        "fecha_pago": p.fecha_pago.isoformat(),
        "cantidad": p.cantidad,
        "precio_unitario": p.precio_unitario,
        "amount_brl": p.amount_brl,
        "type": p.type,
        "instrument_id": item.instrument_id,
        "instrument_name": item.instrument_name,
        "instrument_ticker": item.instrument_ticker,
        "existing_amount_brl": item.existing_amount_brl,
        "match_candidates": item.match_candidates,
        "warnings": item.warnings,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/preview")
async def preview_import(
    file: UploadFile = File(...),
    period_label: str = Form(""),
    db: Session = Depends(get_db),
):
    """
    Step 1: Parse the Excel file and compute a diff preview.
    Returns a file_token valid for 30 minutes to use in /confirm.
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=422, detail="El archivo debe ser .xlsx o .xls")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=422, detail="El archivo está vacío")

    try:
        parsed = parse_excel(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error parseando Excel: {e}")

    if not parsed.items:
        raise HTTPException(
            status_code=422,
            detail="No se encontraron proventos. Verificar que el archivo contiene la hoja 'Proventos Recebidos'."
        )

    try:
        diff_report = compute_diff(parsed, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculando diff: {e}")

    token, expires = store_preview(diff_report, period_label)

    # Summary counts
    items = diff_report.items
    summary = {
        "total_in_file": len(items),
        "total_amount_brl": parsed.total_calculated,
        "total_validated": parsed.total_validated,
        "new": sum(1 for i in items if i.status == "NEW"),
        "duplicates": sum(1 for i in items if i.status == "DUPLICATE"),
        "conflicts": sum(1 for i in items if i.status == "CONFLICT"),
        "no_match": sum(1 for i in items if i.status == "NO_MATCH"),
        "ambiguous_match": sum(1 for i in items if i.status == "AMBIGUOUS_MATCH"),
    }

    return {
        "file_token": token,
        "period_label": period_label,
        "expires_at": expires.isoformat(),
        "summary": summary,
        "differences": [_serialize_diff_item(i) for i in items],
        "parse_warnings": diff_report.parse_warnings,
    }


@router.post("/confirm")
def confirm_import(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Step 2: Apply the confirmed import using the preview token.
    """
    entry = load_preview(body.file_token)
    if entry is None:
        raise HTTPException(
            status_code=410,
            detail="El token de importación expiró (30 min) o no es válido. Volvé a cargar el archivo."
        )

    diff_report = entry["diff_report"]
    period_label = body.period_label or entry.get("period_label", "")

    try:
        result = apply_import(
            diff_report=diff_report,
            force_duplicates=body.force_duplicates,
            skip_indices=body.skip_indices,
            manual_mappings=[m.dict() for m in body.manual_mappings],
            period_label=period_label,
            source_file="",
            db=db,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar la importación: {e}")

    return {
        "success": result.success,
        "batch_id": result.batch_id,
        "imported": {"new": result.imported_new, "overwritten": result.imported_overwritten},
        "skipped": {
            "duplicates": result.skipped_duplicates,
            "no_match": result.skipped_no_match,
            "manual_skip": result.skipped_manual,
        },
        "total_amount_imported": result.total_amount_imported,
        "warnings": result.warnings,
    }


@router.post("/map-instrument")
def map_instrument(
    body: MapInstrumentRequest,
    db: Session = Depends(get_db),
):
    """Assign an instrument_id to a NO_MATCH or AMBIGUOUS_MATCH item in the preview session."""
    entry = load_preview(body.file_token)
    if entry is None:
        raise HTTPException(status_code=410, detail="Token expirado o inválido")

    ok = update_diff_item_mapping(body.file_token, body.index, body.instrument_id, db)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Ítem con índice {body.index} no encontrado")

    return {"ok": True}


@router.delete("/batch/{batch_id}")
def revert_batch(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete all ProvéntoItems from a given batch.
    Only allowed within 24 hours of import.
    """
    batch = db.query(ProventoImportBatch).filter(ProventoImportBatch.id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Lote {batch_id} no encontrado")

    # Check 24-hour limit
    imported_at = datetime.fromisoformat(batch.imported_at)
    if datetime.utcnow() - imported_at > timedelta(hours=24):
        raise HTTPException(
            status_code=403,
            detail="Solo se puede revertir un lote dentro de las 24 horas posteriores a la importación."
        )

    deleted = (
        db.query(ProvéntoItem)
        .filter(ProvéntoItem.import_batch_id == batch_id)
        .delete(synchronize_session=False)
    )
    db.delete(batch)
    db.commit()

    return {"deleted": deleted, "batch_id": batch_id}


@router.get("/batches")
def list_batches(db: Session = Depends(get_db)):
    """List import batch history, most recent first."""
    batches = (
        db.query(ProventoImportBatch)
        .order_by(ProventoImportBatch.imported_at.desc())
        .all()
    )
    return [
        {
            "id": b.id,
            "imported_at": b.imported_at,
            "period_label": b.period_label,
            "source_file": b.source_file,
            "total_amount": b.total_amount,
            "record_count": b.record_count,
        }
        for b in batches
    ]
