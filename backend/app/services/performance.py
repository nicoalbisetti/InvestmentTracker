"""
Performance calculation utilities.
"""
import math
from typing import List, Optional


def calculate_cagr(initial: float, final: float, years: float) -> Optional[float]:
    """Compound Annual Growth Rate."""
    if initial <= 0 or final <= 0 or years <= 0:
        return None
    return (final / initial) ** (1 / years) - 1


def calculate_drawdown(values: List[float]) -> Optional[float]:
    """Maximum drawdown from a series of values."""
    if not values:
        return None
    max_drawdown = 0.0
    peak = values[0]
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak
            if dd < max_drawdown:
                max_drawdown = dd
    return max_drawdown


def calculate_volatility(returns: List[float]) -> Optional[float]:
    """Annualized volatility from monthly returns."""
    if len(returns) < 2:
        return None
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    monthly_std = math.sqrt(variance)
    return monthly_std * math.sqrt(12)


def calculate_cumulative_return(initial: float, final: float) -> Optional[float]:
    if initial is None or final is None or initial == 0:
        return None
    return (final - initial) / initial
