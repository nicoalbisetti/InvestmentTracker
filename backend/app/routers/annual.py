from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.annual_summary import AnnualSummary
from app.models.portfolio_snapshot import PortfolioSnapshot
from datetime import date

router = APIRouter(prefix="/api/annual", tags=["annual"])


@router.get("")
def get_annual_summary(db: Session = Depends(get_db)):
    summaries = (
        db.query(AnnualSummary)
        .order_by(AnnualSummary.year.asc())
        .all()
    )

    # The stored `total` for year N is the START of year N (= Dec of year N-1).
    # We rebuild end-of-year values from portfolio_snapshots (Dec of each year).
    from sqlalchemy import func
    dec_snapshots = (
        db.query(PortfolioSnapshot)
        .filter(func.strftime("%m", PortfolioSnapshot.date) == "12")
        .all()
    )
    end_by_year = {
        s.date.year: (s.total_with_prev or s.total_brl or 0)
        for s in dec_snapshots
    }

    current_year = date.today().year
    latest_snapshot = (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.date.desc())
        .first()
    )
    if latest_snapshot:
        end_by_year[current_year] = (
            latest_snapshot.total_with_prev or latest_snapshot.total_brl or 0
        )

    # start-of-year = end of previous year
    start_by_year = {yr: end_by_year.get(yr - 1) for yr in end_by_year}
    # Also cover years that only exist in annual_summaries
    for s in summaries:
        if s.year not in start_by_year:
            start_by_year[s.year] = s.total

    items = []
    for s in summaries:
        end_total = end_by_year.get(s.year)
        start_total = start_by_year.get(s.year) or s.total
        diff = (end_total - start_total) if (end_total and start_total) else s.diff

        items.append({
            "year": s.year,
            "total": end_total,
            "start_total": start_total,
            "diff": diff,
            "gain": s.gain,
            "net_flow": s.net_flow,
        })

    # Global metrics
    total_invested = sum(i["net_flow"] or 0 for i in items)
    total_gained = sum(i["gain"] or 0 for i in items)

    return {
        "items": items,
        "metrics": {
            "total_invested": total_invested,
            "total_gained": total_gained,
            "gain_ratio": (total_gained / total_invested) if total_invested > 0 else None,
        },
    }
