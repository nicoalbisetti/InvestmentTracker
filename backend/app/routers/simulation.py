from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from dateutil.relativedelta import relativedelta
from app.database import get_db
from app.models.monthly_position import MonthlyPosition
from app.models.instrument import Instrument

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

INTERNATIONAL_CUSTODIANS = {"XP_INTERNATIONAL", "XP_INTERNACIONAL"}


def _classify(instrument: Instrument) -> str | None:
    if instrument.custodian in INTERNATIONAL_CUSTODIANS:
        return "internacional"
    if instrument.type == "renta_fija":
        return "renta_fija"
    if instrument.type == "accion" and instrument.custodian not in INTERNATIONAL_CUSTODIANS:
        return "accion"
    if instrument.type in ("fii", "fundo"):
        return instrument.type
    return None


def _brl_value(pos: MonthlyPosition) -> float:
    if pos.balance_brl is not None:
        return pos.balance_brl
    if pos.balance_usd is not None and pos.usd_rate is not None:
        return pos.balance_usd * pos.usd_rate
    return 0.0


@router.get("")
def get_simulation(
    horizon_months: int = Query(60, ge=1, le=120),
    monthly_contribution_brl: float = Query(0.0, ge=0),
    rate_renta_fija: float = Query(0.13, ge=0, le=10),
    rate_accion: float = Query(0.12, ge=0, le=10),
    rate_fii: float = Query(0.10, ge=0, le=10),
    rate_fundo: float = Query(0.11, ge=0, le=10),
    rate_internacional: float = Query(0.10, ge=0, le=10),
    db: Session = Depends(get_db),
):
    # Subquery: latest date per instrument (ignore custodian_override rows)
    max_date_sub = (
        db.query(
            MonthlyPosition.instrument_id.label("iid"),
            func.max(MonthlyPosition.date).label("mdate"),
        )
        .filter(MonthlyPosition.custodian_override.is_(None))
        .group_by(MonthlyPosition.instrument_id)
        .subquery()
    )

    rows = (
        db.query(MonthlyPosition, Instrument)
        .join(Instrument, MonthlyPosition.instrument_id == Instrument.id)
        .join(
            max_date_sub,
            (MonthlyPosition.instrument_id == max_date_sub.c.iid)
            & (MonthlyPosition.date == max_date_sub.c.mdate),
        )
        .filter(
            MonthlyPosition.custodian_override.is_(None),
            Instrument.status == "activo",
        )
        .all()
    )

    classes = ["renta_fija", "accion", "fii", "fundo", "internacional"]
    class_values: dict[str, float] = {c: 0.0 for c in classes}
    snapshot_date: date | None = None

    for pos, inst in rows:
        cls = _classify(inst)
        if cls is None:
            continue
        class_values[cls] += _brl_value(pos)
        if snapshot_date is None or pos.date > snapshot_date:
            snapshot_date = pos.date

    total_initial = sum(class_values.values())
    ref_date = snapshot_date or date.today()

    if total_initial == 0:
        return {
            "snapshot_date": ref_date.isoformat(),
            "initial_total_brl": 0.0,
            "data": [],
        }

    proportions = {c: class_values[c] / total_initial for c in classes}

    annual_rates = {
        "renta_fija": rate_renta_fija,
        "accion": rate_accion,
        "fii": rate_fii,
        "fundo": rate_fundo,
        "internacional": rate_internacional,
    }
    monthly_rates = {c: (1 + annual_rates[c]) ** (1 / 12) - 1 for c in classes}

    current = {c: class_values[c] for c in classes}
    data = [
        {
            "month": 0,
            "date": f"{ref_date.year}-{ref_date.month:02d}",
            "total": round(total_initial, 2),
            **{c: round(current[c], 2) for c in classes},
        }
    ]

    for i in range(1, horizon_months + 1):
        next_date = ref_date + relativedelta(months=i)
        for c in classes:
            current[c] = (
                current[c] * (1 + monthly_rates[c])
                + monthly_contribution_brl * proportions[c]
            )
        data.append(
            {
                "month": i,
                "date": f"{next_date.year}-{next_date.month:02d}",
                "total": round(sum(current.values()), 2),
                **{c: round(current[c], 2) for c in classes},
            }
        )

    return {
        "snapshot_date": ref_date.isoformat(),
        "initial_total_brl": round(total_initial, 2),
        "data": data,
    }
