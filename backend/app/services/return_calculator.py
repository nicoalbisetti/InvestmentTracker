from datetime import date
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.models.monthly_position import MonthlyPosition
from app.models.transaction import Transaction

PRICE_TYPES = {"accion", "fii"}
ALLOWED_GAP_DAYS = 45


def compute_period_return(
    instrument_id: int,
    instrument_type: str,
    latest_date: date,
    n_months: int,
    db: Session,
) -> Optional[float]:
    """
    Compute the return of an instrument over the last n_months ending at latest_date.

    - accion / fii: price-based return (unit_price change, excludes buy/sell flows).
    - others: balance-based return using Modified Dietz with net flow from transactions.

    Returns None if data is insufficient or the gap to the reference month exceeds 45 days.
    """
    target_date = latest_date - relativedelta(months=n_months)

    if instrument_type in PRICE_TYPES:
        # --- Price-based branch ---
        mp_actual = (
            db.query(MonthlyPosition)
            .filter(
                MonthlyPosition.instrument_id == instrument_id,
                MonthlyPosition.date == latest_date,
                MonthlyPosition.unit_price.isnot(None),
            )
            .first()
        )
        if mp_actual is None or mp_actual.unit_price is None:
            return None

        mp_prev = (
            db.query(MonthlyPosition)
            .filter(
                MonthlyPosition.instrument_id == instrument_id,
                MonthlyPosition.date <= target_date,
                MonthlyPosition.balance_brl > 0,
                MonthlyPosition.unit_price.isnot(None),
            )
            .order_by(MonthlyPosition.date.desc())
            .first()
        )
        if mp_prev is None:
            return None

        if abs((mp_prev.date - target_date).days) > ALLOWED_GAP_DAYS:
            return None

        if mp_prev.unit_price == 0:
            return None

        return (mp_actual.unit_price - mp_prev.unit_price) / mp_prev.unit_price

    else:
        # --- Balance-based branch (Modified Dietz) ---
        mp_actual = (
            db.query(MonthlyPosition)
            .filter(
                MonthlyPosition.instrument_id == instrument_id,
                MonthlyPosition.date == latest_date,
            )
            .first()
        )
        if mp_actual is None or mp_actual.balance_brl is None or mp_actual.balance_brl <= 0:
            return None

        mp_prev = (
            db.query(MonthlyPosition)
            .filter(
                MonthlyPosition.instrument_id == instrument_id,
                MonthlyPosition.date <= target_date,
                MonthlyPosition.balance_brl > 0,
            )
            .order_by(MonthlyPosition.date.desc())
            .first()
        )
        if mp_prev is None:
            return None

        if abs((mp_prev.date - target_date).days) > ALLOWED_GAP_DAYS:
            return None

        # Net flow from transactions in the period.
        # Upper bound is the first day of the month AFTER latest_date so that
        # transactions dated anywhere within the latest month are included.
        period_end = latest_date + relativedelta(months=1)
        flows = (
            db.query(Transaction.type, func.sum(Transaction.amount_brl))
            .filter(
                Transaction.instrument_id == instrument_id,
                Transaction.date >= mp_prev.date + relativedelta(months=1),
                Transaction.date < period_end,
                Transaction.type.in_(["aplicacion", "rescate"]),
            )
            .group_by(Transaction.type)
            .all()
        )
        net_flow = 0.0
        for t_type, t_sum in flows:
            if t_sum is None:
                continue
            if t_type == "aplicacion":
                net_flow += t_sum
            elif t_type == "rescate":
                net_flow -= t_sum

        adjusted_base = (mp_prev.balance_brl or 0) + net_flow * 0.5
        if adjusted_base <= 0:
            return None

        return ((mp_actual.balance_brl or 0) - (mp_prev.balance_brl or 0) - net_flow) / adjusted_base
