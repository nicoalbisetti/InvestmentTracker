from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db
from app.models.provento import Provento
from app.models.instrument import Instrument
from datetime import date

router = APIRouter(prefix="/api/proventos", tags=["proventos"])


@router.get("")
def get_proventos(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Proventos anuales por instrumento."""
    current_year = date.today().year
    years = list(range(current_year, current_year - 7, -1))

    # Get all instruments with any provento
    insts_with_prov = (
        db.query(Instrument.id)
        .join(Provento, Provento.instrument_id == Instrument.id)
        .distinct()
        .all()
    )
    inst_ids = [r[0] for r in insts_with_prov]
    total = len(inst_ids)

    paginated_ids = inst_ids[(page - 1) * limit: page * limit]

    # Get all proventos for these instruments (annual totals only)
    proventos = (
        db.query(Provento)
        .filter(Provento.instrument_id.in_(paginated_ids), Provento.month.is_(None))
        .all()
    )
    prov_map = {}
    for p in proventos:
        prov_map[(p.instrument_id, p.year)] = p.amount

    instruments = db.query(Instrument).filter(Instrument.id.in_(paginated_ids)).all()
    inst_map = {i.id: i for i in instruments}

    items = []
    for inst_id in paginated_ids:
        inst = inst_map.get(inst_id)
        if not inst:
            continue
        row = {
            "id": inst.id,
            "name": inst.name,
            "custodian": inst.custodian,
            "balance_brl": inst.current_balance_brl,
            "years": {yr: prov_map.get((inst_id, yr)) for yr in years},
            "total": sum(v for v in [prov_map.get((inst_id, yr)) for yr in years] if v),
        }
        items.append(row)

    # Sort by total descending
    items.sort(key=lambda x: x["total"] or 0, reverse=True)

    return {
        "items": items,
        "years": years,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/monthly")
def get_monthly_proventos(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Proventos mensuales del anio actual o especificado."""
    target_year = year or date.today().year

    monthly = (
        db.query(Provento.month, func.sum(Provento.amount))
        .filter(Provento.year == target_year, Provento.month.isnot(None))
        .group_by(Provento.month)
        .order_by(Provento.month.asc())
        .all()
    )

    # YTD comparison
    prev_year_total = (
        db.query(func.sum(Provento.amount))
        .filter(Provento.year == target_year - 1, Provento.month.is_(None))
        .scalar()
        or 0
    )
    current_year_total = (
        db.query(func.sum(Provento.amount))
        .filter(Provento.year == target_year, Provento.month.is_(None))
        .scalar()
        or 0
    )

    # Projection: average of last 12 months * 12
    recent_monthly = (
        db.query(func.sum(Provento.amount))
        .filter(Provento.month.isnot(None))
        .scalar()
        or 0
    )
    count_monthly = (
        db.query(Provento)
        .filter(Provento.month.isnot(None))
        .count()
    )
    avg_monthly = (recent_monthly / count_monthly) if count_monthly > 0 else 0
    projection = avg_monthly * 12

    months_map = {m: amt for m, amt in monthly}
    month_series = [
        {"month": m, "amount": months_map.get(m, 0)}
        for m in range(1, 13)
    ]

    return {
        "year": target_year,
        "monthly": month_series,
        "total": current_year_total,
        "prev_year_total": prev_year_total,
        "projection_annual": projection,
    }
