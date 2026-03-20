import io
import csv
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.instrument import Instrument

router = APIRouter(prefix="/api/positions", tags=["positions"])


def _filter_instruments(
    db: Session,
    custodian: Optional[str],
    type: Optional[str],
    currency: Optional[str],
    status: Optional[str],
    search: Optional[str],
    sort: str,
    order: str,
):
    query = db.query(Instrument)

    if status:
        query = query.filter(Instrument.status == status)
    else:
        query = query.filter(Instrument.status == "activo")

    if custodian:
        query = query.filter(Instrument.custodian.ilike(f"%{custodian}%"))
    if type:
        query = query.filter(Instrument.type == type)
    if currency:
        query = query.filter(Instrument.currency == currency)
    if search:
        query = query.filter(Instrument.name.ilike(f"%{search}%"))

    # Sorting
    sort_field = getattr(Instrument, sort, None)
    if sort_field is None:
        sort_field = Instrument.current_balance_brl
    if order == "asc":
        query = query.order_by(sort_field.asc().nullslast())
    else:
        query = query.order_by(sort_field.desc().nullslast())

    return query


@router.get("")
def get_positions(
    custodian: Optional[str] = None,
    type: Optional[str] = None,
    currency: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = Query("current_balance_brl"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = _filter_instruments(db, custodian, type, currency, status, search, sort, order)
    total = query.count()
    instruments = query.offset((page - 1) * limit).limit(limit).all()

    items = []
    for inst in instruments:
        items.append({
            "id": inst.id,
            "name": inst.name,
            "custodian": inst.custodian,
            "type": inst.type,
            "currency": inst.currency,
            "status": inst.status,
            "balance_brl": inst.current_balance_brl,
            "portfolio_pct": inst.portfolio_pct,
            "return_1m": inst.return_1m,
            "return_3m": inst.return_3m,
            "return_6m": inst.return_6m,
            "return_12m": inst.return_12m,
            "rank_1m": inst.rank_1m,
            "liquidity": inst.liquidity,
            "maturity_date": inst.maturity_date.isoformat() if inst.maturity_date else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/export")
def export_positions(
    custodian: Optional[str] = None,
    type: Optional[str] = None,
    currency: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = _filter_instruments(db, custodian, type, currency, status, search, "current_balance_brl", "desc")
    instruments = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Instrumento", "Custodio", "Tipo", "Moneda", "Estado",
        "Saldo BRL", "% Portfolio", "Ret 1M", "Ret 3M", "Ret 6M", "Ret 12M",
        "Rank 1M", "Liquidez", "Vencimiento"
    ])
    for inst in instruments:
        writer.writerow([
            inst.name, inst.custodian, inst.type, inst.currency, inst.status,
            inst.current_balance_brl, inst.portfolio_pct,
            inst.return_1m, inst.return_3m, inst.return_6m, inst.return_12m,
            inst.rank_1m, inst.liquidity,
            inst.maturity_date.isoformat() if inst.maturity_date else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=posiciones.csv"},
    )
