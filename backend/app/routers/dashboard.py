from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.monthly_position import MonthlyPosition
from app.models.instrument import Instrument
from app.models.provento import Provento
from app.models.annual_summary import AnnualSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/kpis")
def get_kpis(db: Session = Depends(get_db)):
    """KPIs principales del portfolio."""
    # Latest snapshot
    latest = (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.date.desc())
        .first()
    )
    prev = (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.date.desc())
        .offset(1)
        .first()
    )

    if not latest:
        return {"error": "No hay datos disponibles"}

    total_brl = latest.total_with_prev or latest.total_brl or 0
    prev_total = (prev.total_with_prev or prev.total_brl or 0) if prev else 0
    monthly_change_abs = total_brl - prev_total if prev_total else 0
    monthly_change_pct = latest.monthly_change_pct

    # YTD: first snapshot of current year
    year_start = (
        db.query(PortfolioSnapshot)
        .filter(func.strftime("%Y", PortfolioSnapshot.date) == str(latest.date.year))
        .order_by(PortfolioSnapshot.date.asc())
        .first()
    )
    ytd_pct = None
    if year_start and year_start.total_with_prev:
        ytd_start = year_start.total_with_prev or year_start.total_brl or 0
        if ytd_start > 0:
            ytd_pct = (total_brl - ytd_start) / ytd_start

    # Proventos del anio actual
    proventos_year = (
        db.query(func.sum(Provento.amount))
        .filter(Provento.year == latest.date.year, Provento.month.is_(None))
        .scalar()
        or 0
    )

    total_usd = latest.total_usd_with_prev or latest.total_usd
    usd_rate = latest.usd_rate

    return {
        "date": latest.date.isoformat(),
        "total_brl": total_brl,
        "total_usd": total_usd,
        "usd_rate": usd_rate,
        "monthly_change_pct": monthly_change_pct,
        "monthly_change_abs": monthly_change_abs,
        "ytd_pct": ytd_pct,
        "proventos_ytd": proventos_year,
    }


@router.get("/evolution")
def get_evolution(
    range: Optional[str] = Query("all", description="1y, 3y, 5y, all"),
    currency: Optional[str] = Query("BRL"),
    db: Session = Depends(get_db),
):
    """Serie historica mensual del portfolio total."""
    query = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.date.asc())

    if range and range != "all":
        from datetime import date
        from dateutil.relativedelta import relativedelta
        years = {"1y": 1, "3y": 3, "5y": 5}.get(range, 99)
        cutoff = date.today().replace(day=1)
        from datetime import timedelta
        # Approximate years in months
        import calendar
        year = cutoff.year - years
        cutoff_date = date(year, cutoff.month, 1)
        query = query.filter(PortfolioSnapshot.date >= cutoff_date)

    snapshots = query.all()
    result = []
    for s in snapshots:
        value = s.total_usd if currency == "USD" else (s.total_with_prev or s.total_brl or 0)
        result.append({
            "date": s.date.isoformat(),
            "value": value,
            "change_pct": s.monthly_change_pct,
        })
    return result


@router.get("/distribution")
def get_distribution(db: Session = Depends(get_db)):
    """Distribucion por tipo de instrumento y por custodio."""
    latest_snap = (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.date.desc())
        .first()
    )
    if not latest_snap:
        return {"by_type": [], "by_custodian": []}

    # By custodian from snapshot
    by_custodian = []
    custodian_fields = [
        ("HSBC", latest_snap.hsbc_total),
        ("Bradesco", latest_snap.bradesco_total),
        ("XP BR", latest_snap.xp_br_total),
        ("XP US", latest_snap.xp_us_total),
        ("Santander", latest_snap.santander_total),
        ("Inter", latest_snap.inter_total),
        ("FGTS", latest_snap.fgts),
        ("Previdencia", latest_snap.prev),
        ("USA", latest_snap.usa_total),
    ]
    for name, val in custodian_fields:
        if val and val > 0:
            by_custodian.append({"name": name, "value": val})

    # By type from active instruments
    from sqlalchemy import case
    type_sums = (
        db.query(Instrument.type, func.sum(Instrument.current_balance_brl))
        .filter(Instrument.status == "activo", Instrument.current_balance_brl > 0)
        .group_by(Instrument.type)
        .all()
    )
    by_type = [{"name": t or "outro", "value": v} for t, v in type_sums if v]

    return {"by_type": by_type, "by_custodian": by_custodian}


@router.get("/top-bottom")
def get_top_bottom(db: Session = Depends(get_db)):
    """Top 5 y Bottom 5 instrumentos del mes por rendimiento."""
    instruments = (
        db.query(Instrument)
        .filter(
            Instrument.status == "activo",
            Instrument.return_1m.isnot(None),
            Instrument.current_balance_brl > 0,
        )
        .all()
    )
    ranked = sorted(instruments, key=lambda x: x.return_1m or 0, reverse=True)

    def serialize(inst):
        return {
            "id": inst.id,
            "name": inst.name,
            "custodian": inst.custodian,
            "type": inst.type,
            "return_1m": inst.return_1m,
            "balance_brl": inst.current_balance_brl,
        }

    return {
        "top5": [serialize(i) for i in ranked[:5]],
        "bottom5": [serialize(i) for i in ranked[-5:]],
    }
