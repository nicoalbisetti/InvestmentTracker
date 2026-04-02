from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.monthly_position import MonthlyPosition
from app.models.instrument import Instrument
from sqlalchemy import func as sqlfunc
from app.models.provento import Provento
from app.models.provento_item import ProvéntoItem
from app.models.provento_forecast import ProventoForecast
from app.models.annual_summary import AnnualSummary
from sqlalchemy import extract

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

    # Proventos del año actual: pagado (provento_items) + proyección (forecast de meses sin pago)
    current_year = latest.date.year
    proventos_year = (
        db.query(func.sum(ProvéntoItem.amount_brl))
        .filter(extract('year', ProvéntoItem.date) == current_year)
        .scalar()
        or 0
    )

    # Forecast for months where each instrument has NOT yet paid
    paid_insts_by_month = db.query(
        extract('month', ProvéntoItem.date).label('m'),
        ProvéntoItem.instrument_id,
    ).filter(extract('year', ProvéntoItem.date) == current_year).distinct().all()
    paid_set = {(int(m), inst_id) for m, inst_id in paid_insts_by_month}

    forecast_rows = db.query(
        ProventoForecast.month, ProventoForecast.instrument_id, ProventoForecast.amount
    ).filter(ProventoForecast.year == current_year).all()

    proventos_projection = proventos_year + sum(
        (amt or 0) for m, inst_id, amt in forecast_rows
        if (m, inst_id) not in paid_set
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
        "proventos_projection": proventos_projection,
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


@router.get("/evolution-by-type")
def get_evolution_by_type(
    range: Optional[str] = Query("all"),
    db: Session = Depends(get_db),
):
    """Serie mensual del portfolio desglosada por tipo de instrumento."""
    from datetime import date

    query = (
        db.query(
            MonthlyPosition.date,
            Instrument.type,
            sqlfunc.sum(MonthlyPosition.balance_brl).label("total"),
        )
        .join(Instrument, MonthlyPosition.instrument_id == Instrument.id)
        .filter(MonthlyPosition.balance_brl > 0)
        .group_by(MonthlyPosition.date, Instrument.type)
        .order_by(MonthlyPosition.date.asc())
    )

    if range and range != "all":
        years = {"1y": 1, "3y": 3, "5y": 5}.get(range, 99)
        cutoff = date(date.today().year - years, date.today().month, 1)
        query = query.filter(MonthlyPosition.date >= cutoff)

    rows = query.all()

    # Collect all types (ordered by total desc for legend)
    type_totals: dict = {}
    data_by_date: dict = {}
    for row in rows:
        date_key = row.date.strftime("%Y-%m")
        t = row.type or "outro"
        data_by_date.setdefault(date_key, {})[t] = (row.total or 0)
        type_totals[t] = type_totals.get(t, 0) + (row.total or 0)

    types = sorted(type_totals.keys(), key=lambda t: type_totals[t], reverse=True)
    dates = sorted(data_by_date.keys())

    result = []
    for d in dates:
        point: dict = {"date": d}
        for t in types:
            point[t] = data_by_date[d].get(t) or None
        result.append(point)

    return {"data": result, "types": types}


@router.get("/benchmarks")
def get_benchmarks(
    range: Optional[str] = Query("all"),
    db: Session = Depends(get_db),
):
    """Retorna taxas mensais CDI e IPCA, usando caché local e buscando só o que falta."""
    from datetime import date
    import requests as req
    from app.models.market_rate import MarketRate

    # Determine date range from portfolio snapshots
    query = db.query(PortfolioSnapshot).order_by(PortfolioSnapshot.date.asc())
    if range and range != "all":
        years = {"1y": 1, "3y": 3, "5y": 5}.get(range, 99)
        cutoff = date(date.today().year - years, date.today().month, 1)
        query = query.filter(PortfolioSnapshot.date >= cutoff)
    snapshots = query.all()

    if not snapshots:
        return {"cdi": [], "ipca": []}

    date_from = snapshots[0].date
    date_to = snapshots[-1].date

    SERIES = {"cdi": 4391, "ipca": 433}

    def fetch_and_cache(series_name: str, series_id: int):
        # Find latest cached date for this series
        row = (
            db.query(MarketRate.date)
            .filter(MarketRate.series == series_name)
            .order_by(MarketRate.date.desc())
            .first()
        )
        latest_cached = row[0] if row else None

        # Only fetch from BCB if we're missing data
        # Fetch from the month after the latest cached, or from the start if nothing cached
        if latest_cached:
            from datetime import datetime
            last_dt = datetime.strptime(latest_cached, "%Y-%m")
            # Advance one month
            if last_dt.month == 12:
                fetch_from = date(last_dt.year + 1, 1, 1)
            else:
                fetch_from = date(last_dt.year, last_dt.month + 1, 1)
        else:
            fetch_from = date(2010, 1, 1)  # fetch all history

        if fetch_from <= date_to:
            url = (
                f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_id}/dados"
                f"?formato=json"
                f"&dataInicial={fetch_from.strftime('%d/%m/%Y')}"
                f"&dataFinal={date_to.strftime('%d/%m/%Y')}"
            )
            try:
                resp = req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                for item in resp.json():
                    try:
                        rate = float(str(item["valor"]).replace(",", ".")) / 100
                        parts = item["data"].split("/")
                        month_key = f"{parts[2]}-{parts[1]}"
                        existing = db.get(MarketRate, (month_key, series_name))
                        if existing:
                            existing.rate = rate
                        else:
                            db.add(MarketRate(date=month_key, series=series_name, rate=rate))
                    except (ValueError, KeyError):
                        continue
                db.commit()
            except Exception:
                db.rollback()

    for name, sid in SERIES.items():
        fetch_and_cache(name, sid)

    # Read from local cache for the requested range
    date_from_key = date_from.strftime("%Y-%m")
    date_to_key = date_to.strftime("%Y-%m")

    rows = (
        db.query(MarketRate)
        .filter(
            MarketRate.date >= date_from_key,
            MarketRate.date <= date_to_key,
        )
        .order_by(MarketRate.date.asc())
        .all()
    )

    result: dict = {"cdi": [], "ipca": []}
    for r in rows:
        result[r.series].append({"date": r.date, "rate": r.rate})

    return result


@router.get("/maturities")
def get_maturities(db: Session = Depends(get_db)):
    """
    Instruments grouped by maturity month, using current_balance_brl.
    Returns months up to 10 years out + a separate list of outliers beyond that.
    """
    from datetime import date
    from dateutil.relativedelta import relativedelta

    today = date.today()
    horizon = today + relativedelta(years=10)

    rows = (
        db.query(Instrument)
        .filter(
            Instrument.status == "activo",
            Instrument.maturity_date.isnot(None),
            Instrument.current_balance_brl.isnot(None),
            Instrument.current_balance_brl > 0,
        )
        .order_by(Instrument.maturity_date.asc())
        .all()
    )

    by_month: dict = {}
    outliers = []

    for inst in rows:
        mat = inst.maturity_date
        # maturity_date may be a string or date
        if isinstance(mat, str):
            from datetime import datetime
            mat = datetime.strptime(mat[:10], "%Y-%m-%d").date()

        month_key = mat.strftime("%Y-%m")

        if mat > horizon:
            outliers.append({
                "name": inst.name,
                "maturity_date": mat.isoformat(),
                "type": inst.type,
                "balance_brl": inst.current_balance_brl,
            })
            continue

        if month_key not in by_month:
            by_month[month_key] = {"month": month_key, "total": 0, "instruments": [], "by_type": {}}

        by_month[month_key]["total"] += inst.current_balance_brl
        by_month[month_key]["by_type"][inst.type or "outro"] = (
            by_month[month_key]["by_type"].get(inst.type or "outro", 0) + inst.current_balance_brl
        )
        by_month[month_key]["instruments"].append({
            "name": inst.name,
            "type": inst.type,
            "balance_brl": round(inst.current_balance_brl, 2),
        })

    # Round totals
    data = []
    all_types: set = set()
    for m in sorted(by_month.keys()):
        entry = by_month[m]
        entry["total"] = round(entry["total"], 2)
        entry["by_type"] = {t: round(v, 2) for t, v in entry["by_type"].items()}
        all_types.update(entry["by_type"].keys())
        data.append(entry)

    return {
        "data": data,
        "types": sorted(all_types),
        "outliers": outliers,
    }


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
