# src/aggregator/oi.py
from src.storage.models import OISnapshot


def calculate_oi_change(current: OISnapshot | None, past: OISnapshot | None) -> float:
    if not current or not past or past.open_interest_usd == 0:
        return 0.0
    return (current.open_interest_usd - past.open_interest_usd) / past.open_interest_usd * 100


def interpret_oi_price(oi_change: float, price_change: float) -> str:
    if oi_change > 1 and price_change > 0:
        return "新多入场"
    elif oi_change > 1 and price_change < 0:
        return "新空入场"
    elif oi_change < -1 and price_change > 0:
        return "空头平仓"
    elif oi_change < -1 and price_change < 0:
        return "多头平仓"
    else:
        return "持仓稳定"
