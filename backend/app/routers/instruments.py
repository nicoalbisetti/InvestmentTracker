from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.instrument import Instrument
from app.schemas.instrument import InstrumentOut, InstrumentUpdate

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


@router.get("")
def get_instruments(
    status: Optional[str] = None,
    type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Instrument)
    if status:
        query = query.filter(Instrument.status == status)
    if type:
        query = query.filter(Instrument.type == type)
    if search:
        query = query.filter(Instrument.name.ilike(f"%{search}%"))
    query = query.order_by(Instrument.name.asc())

    total = query.count()
    instruments = query.offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [InstrumentOut.model_validate(i).model_dump() for i in instruments],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/{instrument_id}")
def get_instrument(instrument_id: int, db: Session = Depends(get_db)):
    inst = db.query(Instrument).filter_by(id=instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    return InstrumentOut.model_validate(inst).model_dump()


@router.put("/{instrument_id}")
def update_instrument(
    instrument_id: int, payload: InstrumentUpdate, db: Session = Depends(get_db)
):
    inst = db.query(Instrument).filter_by(id=instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")

    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(inst, k, v)
    db.commit()
    return {"message": "Instrumento actualizado"}
