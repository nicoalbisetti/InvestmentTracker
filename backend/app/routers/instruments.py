from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from pydantic import BaseModel
from app.database import get_db
from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from app.models.transaction import Transaction
from app.models.quote import Quote
from app.schemas.instrument import InstrumentOut, InstrumentUpdate, InstrumentCreate
from app.services.snapshot_sync import sync_snapshot_for_date, resync_portfolio_totals

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


@router.get("")
def get_instruments(
    status: Optional[str] = None,
    type: Optional[str] = None,
    location: Optional[str] = None,
    currency: Optional[str] = None,
    custodian: Optional[str] = None,
    no_maturity: bool = Query(False),
    search: Optional[str] = None,
    with_position: bool = Query(False),
    sort: Optional[str] = Query("name"),
    order: Optional[str] = Query("asc"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    SORTABLE = {
        "name": Instrument.name,
        "ticker": Instrument.ticker,
        "custodian": Instrument.custodian,
        "type": Instrument.type,
        "status": Instrument.status,
        "maturity_date": Instrument.maturity_date,
    }
    query = db.query(Instrument)
    if status:
        query = query.filter(Instrument.status == status)
    if type:
        query = query.filter(Instrument.type == type)
    if location:
        query = query.filter(Instrument.location == location)
    if currency:
        query = query.filter(Instrument.currency == currency)
    if custodian:
        query = query.filter(Instrument.custodian == custodian)
    if no_maturity:
        query = query.filter(Instrument.maturity_date.is_(None))
    if search:
        query = query.filter(Instrument.name.ilike(f"%{search}%"))
    if with_position:
        query = query.filter(
            Instrument.current_balance_brl.isnot(None),
            Instrument.current_balance_brl > 0,
        )
    col = SORTABLE.get(sort or "name", Instrument.name)
    query = query.order_by(col.desc() if order == "desc" else col.asc())

    total = query.count()
    instruments = query.offset((page - 1) * limit).limit(limit).all()

    return {
        "items": [InstrumentOut.model_validate(i).model_dump() for i in instruments],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("")
def create_instrument(payload: InstrumentCreate, db: Session = Depends(get_db)):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío.")
    if not payload.custodian.strip():
        raise HTTPException(status_code=400, detail="El custodio no puede estar vacío.")
    if payload.balance_brl is not None and not payload.initial_period:
        raise HTTPException(status_code=422, detail="Se requiere el período cuando se provee un saldo inicial.")
    if payload.initial_period:
        import re
        if not re.match(r"^\d{4}-\d{2}$", payload.initial_period):
            raise HTTPException(status_code=422, detail="El período debe tener formato YYYY-MM.")

    # Check duplicate
    existing = db.query(Instrument).filter_by(name=payload.name.strip(), custodian=payload.custodian.strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un instrumento con ese nombre y custodio.")

    warnings: list[str] = []

    try:
        inst = Instrument(
            name=payload.name.strip(),
            custodian=payload.custodian.strip(),
            type=payload.type,
            currency=payload.currency,
            status=payload.status,
            location=payload.location,
            liquidity=payload.liquidity,
            maturity_date=payload.maturity_date,
            index_type=payload.index_type,
            asset_class=payload.asset_class,
        )
        db.add(inst)
        db.flush()  # get inst.id without committing

        position_created = False
        balance_usd = None

        if payload.balance_brl is not None:
            year, month = map(int, payload.initial_period.split("-"))
            pos_date = date(year, month, 1)

            quote = db.query(Quote).filter_by(date=pos_date).first()
            usd_rate = None
            if quote and quote.usd_brl:
                balance_usd = round(payload.balance_brl / quote.usd_brl, 2)
                usd_rate = quote.usd_brl
            else:
                warnings.append(f"Sin cotización USD/BRL para {payload.initial_period} — balance_usd no calculado")

            pos = MonthlyPosition(
                instrument_id=inst.id,
                date=pos_date,
                balance_brl=payload.balance_brl,
                balance_usd=balance_usd,
                usd_rate=usd_rate,
            )
            db.add(pos)
            inst.current_balance_brl = payload.balance_brl
            position_created = True
            db.flush()
            sync_snapshot_for_date(db, pos_date)
            resync_portfolio_totals(db)

        db.commit()
        db.refresh(inst)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al crear el instrumento.")

    return {
        "id": inst.id,
        "name": inst.name,
        "custodian": inst.custodian,
        "position_created": position_created,
        "balance_usd": balance_usd,
        "warnings": warnings,
        "message": "Instrumento creado correctamente",
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


class RescateTotalPayload(BaseModel):
    date: date


@router.post("/{instrument_id}/rescate-total")
def rescate_total(instrument_id: int, payload: RescateTotalPayload, db: Session = Depends(get_db)):
    inst = db.query(Instrument).filter_by(id=instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    if inst.status == "cerrado":
        raise HTTPException(status_code=400, detail="El instrumento ya está cerrado.")
    if inst.type != "renta_fija":
        raise HTTPException(status_code=400, detail="El rescate total solo está disponible para instrumentos de renta fija.")

    # Take balances from the most recent monthly position (not the stale cache on the instrument)
    latest_pos = (
        db.query(MonthlyPosition)
        .filter_by(instrument_id=inst.id)
        .order_by(MonthlyPosition.date.desc())
        .first()
    )
    amount_brl = latest_pos.balance_brl if latest_pos else inst.current_balance_brl
    amount_usd = latest_pos.balance_usd if latest_pos else None

    try:
        txn = Transaction(
            instrument_id=inst.id,
            date=payload.date,
            type="rescate",
            amount_brl=amount_brl,
            amount_usd=amount_usd if amount_usd else None,
            notes="Rescate total (automático)",
        )
        db.add(txn)

        # Zero out the monthly position so the balance reflects the rescate
        if latest_pos:
            latest_pos.balance_brl = 0
            latest_pos.balance_usd = 0

        inst.status = "cerrado"
        inst.current_balance_brl = 0

        db.commit()
        db.refresh(txn)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al procesar el rescate.")

    return {
        "message": "Rescate total registrado",
        "transaction_id": txn.id,
        "instrument_id": inst.id,
        "instrument_name": inst.name,
    }
