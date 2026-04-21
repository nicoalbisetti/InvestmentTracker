from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db
from app.models.provento import Provento
from app.models.provento_forecast import ProventoForecast
from app.models.provento_item import ProvéntoItem
from app.models.instrument import Instrument
from app.models.monthly_position import MonthlyPosition
from datetime import date
from sqlalchemy import extract

router = APIRouter(prefix="/api/proventos", tags=["proventos"])

TYPE_ORDER = ["accion", "fii", "renta_fija", "fundo", "previdencia", "prestamos", "saving", "fgts", "outro"]


@router.get("")
def get_proventos(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query("activo"),
    db: Session = Depends(get_db),
):
    """Proventos anuales por instrumento."""
    current_year = date.today().year
    years = list(range(current_year, current_year - 7, -1))

    # Get instruments with proventos (from proventos table) OR provento_items (current year)
    hist_ids = {r[0] for r in (
        db.query(Instrument.id)
        .join(Provento, Provento.instrument_id == Instrument.id)
        .distinct()
        .all()
    )}
    curr_ids = {r[0] for r in (
        db.query(ProvéntoItem.instrument_id)
        .filter(extract('year', ProvéntoItem.date) == current_year)
        .distinct()
        .all()
    )}
    all_inst_ids_query = db.query(Instrument.id).filter(
        Instrument.id.in_(hist_ids | curr_ids)
    )
    if status:
        all_inst_ids_query = all_inst_ids_query.filter(Instrument.status == status)
    inst_ids = [r[0] for r in all_inst_ids_query.all()]
    total = len(inst_ids)

    paginated_ids = inst_ids[(page - 1) * limit: page * limit]

    # Historical proventos from proventos table (past years only — current year uses provento_items)
    proventos = (
        db.query(Provento)
        .filter(
            Provento.instrument_id.in_(paginated_ids),
            Provento.month.is_(None),
            Provento.year < current_year,
        )
        .all()
    )
    prov_map = {}
    for p in proventos:
        prov_map[(p.instrument_id, p.year)] = p.amount

    # Override with provento_items for any year that has records there
    items_by_year = (
        db.query(
            ProvéntoItem.instrument_id,
            extract('year', ProvéntoItem.date).label('year'),
            func.sum(ProvéntoItem.amount_brl),
        )
        .filter(ProvéntoItem.instrument_id.in_(paginated_ids))
        .group_by(ProvéntoItem.instrument_id, extract('year', ProvéntoItem.date))
        .all()
    )
    for inst_id, yr, amt in items_by_year:
        prov_map[(inst_id, int(yr))] = amt

    # For current year: add forecast for months where the instrument hasn't paid yet
    paid_months_per_inst: dict[int, set] = {}
    paid_months_rows = (
        db.query(
            ProvéntoItem.instrument_id,
            extract('month', ProvéntoItem.date).label('month'),
        )
        .filter(
            ProvéntoItem.instrument_id.in_(paginated_ids),
            extract('year', ProvéntoItem.date) == current_year,
        )
        .distinct()
        .all()
    )
    for inst_id, m in paid_months_rows:
        paid_months_per_inst.setdefault(inst_id, set()).add(int(m))

    forecast_rows_full = (
        db.query(ProventoForecast.instrument_id, ProventoForecast.month, ProventoForecast.amount)
        .filter(
            ProventoForecast.instrument_id.in_(paginated_ids),
            ProventoForecast.year == current_year,
        )
        .all()
    )
    for inst_id, month, amt in forecast_rows_full:
        if month not in paid_months_per_inst.get(inst_id, set()):
            existing = prov_map.get((inst_id, current_year), 0) or 0
            prov_map[(inst_id, current_year)] = existing + (amt or 0)

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
            "type": inst.type,
            "custodian": inst.custodian,
            "balance_brl": inst.current_balance_brl,
            "years": {yr: prov_map.get((inst_id, yr)) for yr in years},
            "total": sum(v for v in [prov_map.get((inst_id, yr)) for yr in years] if v),
        }
        items.append(row)

    # Sort by type order, then by total desc within type
    items.sort(key=lambda x: (TYPE_ORDER.index(x["type"]) if x["type"] in TYPE_ORDER else 99, -(x["total"] or 0)))

    # Column totals
    year_totals = {yr: sum(row["years"].get(yr) or 0 for row in items) for yr in years}
    balance_total = sum(row["balance_brl"] or 0 for row in items)

    # Latest position date (what month does balance_brl correspond to)
    latest_pos_date = (
        db.query(func.max(MonthlyPosition.date))
        .join(Instrument, Instrument.id == MonthlyPosition.instrument_id)
        .filter(Instrument.status == (status or "activo"))
        .scalar()
    )

    return {
        "items": items,
        "years": years,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "year_totals": year_totals,
        "balance_total": balance_total,
        "positions_as_of": latest_pos_date.isoformat() if latest_pos_date else None,
    }


@router.get("/monthly")
def get_monthly_proventos(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Proventos mensuales del anio actual o especificado."""
    target_year = year or date.today().year

    # Paid per month
    items_monthly = (
        db.query(extract('month', ProvéntoItem.date).label('m'), func.sum(ProvéntoItem.amount_brl))
        .filter(extract('year', ProvéntoItem.date) == target_year)
        .group_by('m')
        .all()
    )
    paid_map = {int(m): (amt or 0) for m, amt in items_monthly}

    # Instruments that paid per month: {month -> set(instrument_id)}
    paid_insts_rows = (
        db.query(extract('month', ProvéntoItem.date).label('m'), ProvéntoItem.instrument_id)
        .filter(extract('year', ProvéntoItem.date) == target_year)
        .distinct()
        .all()
    )
    paid_insts: dict[int, set] = {}
    for m, inst_id in paid_insts_rows:
        paid_insts.setdefault(int(m), set()).add(inst_id)

    # Forecast for instruments that have NOT yet paid that month
    forecast_rows = (
        db.query(ProventoForecast.month, ProventoForecast.instrument_id, ProventoForecast.amount)
        .filter(ProventoForecast.year == target_year)
        .all()
    )
    forecast_unpaid_map: dict[int, float] = {}
    for m, inst_id, amt in forecast_rows:
        if inst_id not in paid_insts.get(m, set()):
            forecast_unpaid_map[m] = forecast_unpaid_map.get(m, 0) + (amt or 0)

    # YTD totals
    prev_year_total = (
        db.query(func.sum(Provento.amount))
        .filter(Provento.year == target_year - 1, Provento.month.is_(None))
        .scalar()
        or 0
    )
    current_year_total = (
        db.query(func.sum(ProvéntoItem.amount_brl))
        .filter(extract('year', ProvéntoItem.date) == target_year)
        .scalar()
        or 0
    )

    month_series = []
    for m in range(1, 13):
        actual = paid_map.get(m) or 0
        forecast = forecast_unpaid_map.get(m) or 0
        month_series.append({
            "month": m,
            "amount": actual,
            "forecast": forecast,
        })

    projection_annual = current_year_total + sum(forecast_unpaid_map.values())

    return {
        "year": target_year,
        "monthly": month_series,
        "total": current_year_total,
        "prev_year_total": prev_year_total,
        "projection_annual": projection_annual,
    }


MONTHS = list(range(1, 13))


@router.get("/grid")
def get_proventos_grid(
    year: int = Query(default=None),
    type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Returns instruments with pays_dividends=True and their monthly paid amounts
    for the given year, aggregated from provento_items (both imported and manual).
    """
    target_year = year or date.today().year

    query = db.query(Instrument).filter(
        Instrument.pays_dividends == True,
        Instrument.status == "activo",
    )
    if type:
        query = query.filter(Instrument.type == type)
    instruments = query.all()

    inst_ids = [i.id for i in instruments]

    # Sum provento_items grouped by (instrument_id, month)
    rows = (
        db.query(
            ProvéntoItem.instrument_id,
            extract('month', ProvéntoItem.date).label('month'),
            func.sum(ProvéntoItem.amount_brl).label('total'),
        )
        .filter(
            ProvéntoItem.instrument_id.in_(inst_ids),
            extract('year', ProvéntoItem.date) == target_year,
        )
        .group_by(ProvéntoItem.instrument_id, extract('month', ProvéntoItem.date))
        .all()
    )
    paid_map: dict[tuple, float] = {(r.instrument_id, int(r.month)): r.total for r in rows}

    # Load forecast for the target year
    forecast_rows = (
        db.query(ProventoForecast.instrument_id, ProventoForecast.month, ProventoForecast.amount)
        .filter(
            ProventoForecast.instrument_id.in_(inst_ids),
            ProventoForecast.year == target_year,
        )
        .all()
    )
    forecast_map: dict[tuple, float] = {(r.instrument_id, r.month): r.amount for r in forecast_rows}

    items = []
    for inst in instruments:
        months = {m: paid_map.get((inst.id, m)) for m in MONTHS}
        # forecast_months: only where there is no paid amount
        forecast_months = {
            m: (forecast_map.get((inst.id, m)) if months[m] is None else None)
            for m in MONTHS
        }
        total = sum(
            (months[m] if months[m] is not None else (forecast_months[m] or 0))
            for m in MONTHS
        )
        items.append({
            "id": inst.id,
            "name": inst.name,
            "type": inst.type,
            "location": inst.location,
            "custodian": inst.custodian,
            "months": months,
            "forecast_months": forecast_months,
            "total": total,
        })

    LOCATION_ORDER = ["brasil", "exterior"]
    items.sort(key=lambda x: (
        LOCATION_ORDER.index(x["location"]) if x["location"] in LOCATION_ORDER else 99,
        TYPE_ORDER.index(x["type"]) if x["type"] in TYPE_ORDER else 99,
        x["name"].lower(),
    ))

    # month_totals: paid + unpaid-forecast per column
    month_totals = {
        m: sum(
            (row["months"].get(m) or 0) if row["months"].get(m) is not None
            else (row["forecast_months"].get(m) or 0)
            for row in items
        )
        for m in MONTHS
    }
    # paid_month_totals: only paid amounts per column (for color differentiation in frontend)
    paid_month_totals = {m: sum(row["months"].get(m) or 0 for row in items) for m in MONTHS}
    grand_total = sum(month_totals.values())

    return {
        "year": target_year,
        "items": items,
        "month_totals": month_totals,
        "paid_month_totals": paid_month_totals,
        "grand_total": grand_total,
    }


@router.patch("/grid/{instrument_id}/{year}/{month}")
def upsert_provento_grid(
    instrument_id: int,
    year: int,
    month: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Replace ALL provento_items for this instrument/month with a single MANUAL record.
    Pass amount=null or 0 to delete everything for that cell.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Mes inválido")

    from datetime import date as date_type
    import calendar
    amount = payload.get("amount")

    # Delete ALL records for this instrument/month (imported + manual)
    db.query(ProvéntoItem).filter(
        ProvéntoItem.instrument_id == instrument_id,
        extract('year', ProvéntoItem.date) == year,
        extract('month', ProvéntoItem.date) == month,
    ).delete(synchronize_session=False)

    if amount is None or amount == 0:
        db.commit()
        return {"deleted": True}

    last_day = calendar.monthrange(year, month)[1]
    db.add(ProvéntoItem(
        instrument_id=instrument_id,
        date=date_type(year, month, last_day),
        amount_brl=float(amount),
        type="dividendo",
        source="MANUAL",
    ))
    db.commit()
    return {"instrument_id": instrument_id, "year": year, "month": month, "amount": float(amount)}
