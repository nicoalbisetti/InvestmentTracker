import os
import shutil
import tempfile
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.import_log import ImportLog
from app.services.importer import import_excel
from datetime import datetime

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("")
async def import_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx, .xls)")

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        report = import_excel(tmp_path, db)
        status = "failed" if report["errors"] else ("partial" if report["warnings"] else "success")

        log = ImportLog(
            filename=file.filename,
            imported_at=datetime.utcnow(),
            status=status,
            records_instruments=report["instruments"],
            records_positions=report["positions"],
            records_snapshots=report["snapshots"],
            records_annual=report["annual"],
            records_proventos=report["proventos"],
            records_quotes=report["quotes"],
            records_ranking=report["ranking"],
            warnings=report["warnings"],
            errors=report["errors"],
        )
        db.add(log)
        db.commit()

        return {
            "status": status,
            "log_id": log.id,
            "records": {
                "instruments_created": report["instruments"],
                "positions": report["positions"],
                "snapshots": report["snapshots"],
                "annual": report["annual"],
                "proventos": report["proventos"],
                "quotes": report["quotes"],
                "ranking_updated": report["ranking"],
            },
            "warnings": report["warnings"],
            "errors": report["errors"],
        }
    finally:
        os.unlink(tmp_path)


@router.get("/history")
def get_import_history(db: Session = Depends(get_db)):
    logs = (
        db.query(ImportLog)
        .order_by(ImportLog.imported_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": l.id,
            "filename": l.filename,
            "imported_at": l.imported_at.isoformat(),
            "status": l.status,
            "records_positions": l.records_positions,
            "records_instruments": l.records_instruments,
            "warning_count": len(l.warnings or []),
            "error_count": len(l.errors or []),
        }
        for l in logs
    ]


@router.get("/history/{log_id}")
def get_import_detail(log_id: int, db: Session = Depends(get_db)):
    log = db.query(ImportLog).filter_by(id=log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log no encontrado")
    return {
        "id": log.id,
        "filename": log.filename,
        "imported_at": log.imported_at.isoformat(),
        "status": log.status,
        "records": {
            "instruments": log.records_instruments,
            "positions": log.records_positions,
            "snapshots": log.records_snapshots,
            "annual": log.records_annual,
            "proventos": log.records_proventos,
            "quotes": log.records_quotes,
            "ranking": log.records_ranking,
        },
        "warnings": log.warnings,
        "errors": log.errors,
    }
