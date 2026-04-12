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


def resync_portfolio_totals(db: Session):
    """
    Recalculate total_with_prev on the latest portfolio snapshot using the
    most recent balance per active instrument across all months.
    Call this after any operation that changes MonthlyPosition balances.
    """
    from app.models.instrument import Instrument

    # Subquery: latest position date per instrument
    max_date_sub = (
        db.query(
            MonthlyPosition.instrument_id.label("iid"),
            func.max(MonthlyPosition.date).label("max_date"),
        )
        .group_by(MonthlyPosition.instrument_id)
        .subquery()
    )

    rows = (
        db.query(MonthlyPosition.balance_brl, MonthlyPosition.balance_usd)
        .join(
            max_date_sub,
            (MonthlyPosition.instrument_id == max_date_sub.c.iid)
            & (MonthlyPosition.date == max_date_sub.c.max_date),
        )
        .join(Instrument, Instrument.id == MonthlyPosition.instrument_id)
        .filter(
            Instrument.status == "activo",
            MonthlyPosition.balance_brl.isnot(None),
            MonthlyPosition.balance_brl > 0,
        )
        .all()
    )

    total = sum(r.balance_brl for r in rows if r.balance_brl)
    total_usd = sum(r.balance_usd for r in rows if r.balance_usd)

    latest_snap = (
        db.query(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.date.desc())
        .first()
    )
    if not latest_snap:
        return

    latest_snap.total_with_prev = total
    if total_usd:
        latest_snap.total_usd_with_prev = total_usd
    elif latest_snap.usd_rate and latest_snap.usd_rate > 0:
        latest_snap.total_usd_with_prev = total / latest_snap.usd_rate

    # Also keep total_brl in sync for the snapshot's own month
    month_total = (
        db.query(func.sum(MonthlyPosition.balance_brl))
        .filter(
            MonthlyPosition.date == latest_snap.date,
            MonthlyPosition.balance_brl.isnot(None),
            MonthlyPosition.balance_brl > 0,
        )
        .scalar() or 0
    )
    latest_snap.total_brl = month_total
    if latest_snap.usd_rate and latest_snap.usd_rate > 0:
        latest_snap.total_usd = month_total / latest_snap.usd_rate
