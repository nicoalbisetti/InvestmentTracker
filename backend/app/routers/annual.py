from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.annual_summary import AnnualSummary

router = APIRouter(prefix="/api/annual", tags=["annual"])


@router.get("")
def get_annual_summary(db: Session = Depends(get_db)):
    summaries = (
        db.query(AnnualSummary)
        .order_by(AnnualSummary.year.asc())
        .all()
    )
    items = []
    for s in summaries:
        items.append({
            "year": s.year,
            "total": s.total,
            "diff": s.diff,
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
