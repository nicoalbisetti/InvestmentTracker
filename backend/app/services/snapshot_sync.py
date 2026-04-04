from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.monthly_position import MonthlyPosition

def sync_snapshot_for_date(db: Session, target_date: date):
    snap = db.query(PortfolioSnapshot).filter_by(date=target_date).first()
    if not snap:
        snap = PortfolioSnapshot(date=target_date)
        db.add(snap)
        db.flush()

    month_total = (
        db.query(func.sum(MonthlyPosition.balance_brl))
        .filter(
            MonthlyPosition.date == target_date,
            MonthlyPosition.balance_brl.isnot(None),
            MonthlyPosition.balance_brl > 0,
        )
        .scalar() or 0
    )
    snap.total_brl = month_total
    if snap.usd_rate and snap.usd_rate > 0:
        snap.total_usd = month_total / snap.usd_rate
    return snap

def sync_all_snapshots(db: Session):
    from sqlalchemy import distinct
    months = db.query(distinct(MonthlyPosition.date)).all()
    for (mdate,) in months:
        sync_snapshot_for_date(db, mdate)
