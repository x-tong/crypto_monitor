# src/alert/price_monitor.py
import time
from dataclasses import dataclass

from src.storage.models import PriceAlert


@dataclass
class PriceAlertResult:
    alert_id: int
    type: str  # "breakout" | "breakdown"
    price: float


def check_price_alerts(
    alerts: list[PriceAlert],
    current_price: float,
    cooldown_seconds: int,
) -> list[PriceAlertResult]:
    results: list[PriceAlertResult] = []
    now = int(time.time())

    for alert in alerts:
        # 检查冷却
        if alert.last_triggered_at:
            if now - alert.last_triggered_at < cooldown_seconds:
                continue

        # 检查突破/跌破
        if alert.last_position == "below" and current_price >= alert.price:
            results.append(
                PriceAlertResult(
                    alert_id=alert.id or 0,
                    type="breakout",
                    price=alert.price,
                )
            )
        elif alert.last_position == "above" and current_price <= alert.price:
            results.append(
                PriceAlertResult(
                    alert_id=alert.id or 0,
                    type="breakdown",
                    price=alert.price,
                )
            )

    return results
