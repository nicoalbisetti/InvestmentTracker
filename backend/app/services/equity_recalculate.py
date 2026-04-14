import logging
from datetime import date
from calendar import monthrange

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.equity_trade import EquityTrade
from app.models.monthly_position import MonthlyPosition
from app.services.snapshot_sync import sync_snapshot_for_date

logger = logging.getLogger(__name__)


def recalculate_equity_positions(instrument_id: int, from_date: date, db: Session) -> int:
    """
    Recalcula MonthlyPosition para instrument_id desde el mes de from_date en adelante.
    Retorna el número de meses recalculados.
    """
    # 1. Normalizar al primer día del mes
    from_month = from_date.replace(day=1)

    # 2. Obtener todas las MonthlyPosition >= from_month ordenadas ASC
    positions = (
        db.query(MonthlyPosition)
        .filter(
            MonthlyPosition.instrument_id == instrument_id,
            MonthlyPosition.date >= from_month,
        )
        .order_by(MonthlyPosition.date.asc())
        .all()
    )

    if not positions:
        logger.info(
            "equity_recalculate: no hay MonthlyPositions para instrument_id=%s desde %s",
            instrument_id, from_month,
        )
        return 0

    # 3. Encontrar la posición del mes inmediatamente anterior al from_month
    prev_pos = (
        db.query(MonthlyPosition)
        .filter(
            MonthlyPosition.instrument_id == instrument_id,
            MonthlyPosition.date < from_month,
        )
        .order_by(MonthlyPosition.date.desc())
        .first()
    )

    running_qty = prev_pos.quantity if prev_pos and prev_pos.quantity is not None else 0.0
    running_avg = prev_pos.avg_price if prev_pos and prev_pos.avg_price is not None else 0.0

    recalculated = 0
    for mp in positions:
        # Obtener los trades de este mes
        last_day = monthrange(mp.date.year, mp.date.month)[1]
        end_of_month = mp.date.replace(day=last_day)
        start_of_month = mp.date.replace(day=1)

        trades_of_month = (
            db.query(EquityTrade)
            .filter(
                EquityTrade.instrument_id == instrument_id,
                EquityTrade.date >= start_of_month,
                EquityTrade.date <= end_of_month,
            )
            .order_by(EquityTrade.date.asc(), EquityTrade.id.asc())
            .all()
        )

        # Aplicar trades iterativamente al running
        for t in trades_of_month:
            if t.trade_type == "compra":
                total_cost_before = running_qty * running_avg
                trade_cost = t.quantity * t.price
                running_qty += t.quantity
                if running_qty > 0:
                    running_avg = (total_cost_before + trade_cost) / running_qty
            elif t.trade_type == "venta":
                running_qty -= t.quantity
                if running_qty < 0:
                    logger.warning("equity_recalculate: quantity negativa tras venta para instrument_id=%s", instrument_id)
                    running_qty = 0.0

        # Actualizar MP
        mp.quantity = running_qty
        mp.avg_price = running_avg if running_qty > 0 and running_avg > 0 else None

        # Si hay unit_price, recalcular balance_brl
        if mp.unit_price is not None:
            mp.balance_brl = round(running_qty * mp.unit_price, 2)

        # Calcular gain y gain_pct con Modified Dietz
        prev_month_date = mp.date - relativedelta(months=1)
        prev_mp = (
            db.query(MonthlyPosition)
            .filter(
                MonthlyPosition.instrument_id == instrument_id,
                MonthlyPosition.date == prev_month_date,
            )
            .first()
        )
        if prev_mp and prev_mp.balance_brl and prev_mp.balance_brl > 0:
            net_trade_flow = sum(
                t.quantity * t.price if t.trade_type == "compra" else -(t.quantity * t.price)
                for t in trades_of_month
            )
            mp.gain = (mp.balance_brl or 0) - (prev_mp.balance_brl or 0) - net_trade_flow
            adjusted_base = (prev_mp.balance_brl or 0) + net_trade_flow * 0.5
            if adjusted_base > 0:
                mp.gain_pct = mp.gain / adjusted_base
            else:
                mp.gain_pct = None
        else:
            mp.gain = None
            mp.gain_pct = None

        db.flush()
        sync_snapshot_for_date(db, mp.date)
        recalculated += 1

    db.flush()
    return recalculated
