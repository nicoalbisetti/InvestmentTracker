import logging
from datetime import date
from calendar import monthrange

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.equity_trade import EquityTrade
from app.models.monthly_position import MonthlyPosition

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

    # Obtener todos los trades del instrumento (necesitamos acumular desde el inicio)
    all_trades = (
        db.query(EquityTrade)
        .filter(EquityTrade.instrument_id == instrument_id)
        .all()
    )

    recalculated = 0
    for mp in positions:
        # Último día del mes de mp.date
        last_day = monthrange(mp.date.year, mp.date.month)[1]
        end_of_month = mp.date.replace(day=last_day)

        # a. Calcular quantity acumulada hasta fin de mes
        qty_compras = sum(
            t.quantity for t in all_trades
            if t.trade_type == "compra" and t.date <= end_of_month
        )
        qty_ventas = sum(
            t.quantity for t in all_trades
            if t.trade_type == "venta" and t.date <= end_of_month
        )
        qty_acumulada = qty_compras - qty_ventas

        if qty_acumulada < 0:
            logger.warning(
                "equity_recalculate: quantity negativa (%.2f) para instrument_id=%s en %s",
                qty_acumulada, instrument_id, mp.date,
            )

        # b. Actualizar quantity
        mp.quantity = qty_acumulada

        # c. Si hay unit_price, recalcular balance_brl
        if mp.unit_price is not None:
            mp.balance_brl = qty_acumulada * mp.unit_price

        # d. Calcular avg_price ponderado (solo compras)
        compras_hasta_mes = [
            t for t in all_trades
            if t.trade_type == "compra" and t.date <= end_of_month
        ]
        if compras_hasta_mes:
            total_qty_compras = sum(t.quantity for t in compras_hasta_mes)
            total_cost = sum(t.quantity * t.price for t in compras_hasta_mes)
            mp.avg_price = total_cost / total_qty_compras if total_qty_compras > 0 else None
        else:
            mp.avg_price = None

        recalculated += 1

    db.flush()
    return recalculated
