# src/aggregator/extreme_tracker.py
import time

from src.aggregator.percentile import calculate_percentile_multi_window
from src.storage.database import Database
from src.storage.models import ExtremeEvent


class ExtremeTracker:
    """极端事件检测与记录"""

    def __init__(self, db: Database, cooldown_hours: int = 1):
        self.db = db
        self.cooldown_hours = cooldown_hours

    def detect_extremes(
        self,
        value: float,
        history: list[float],
        threshold: float = 90,
        windows: list[int] | None = None,
    ) -> dict[str, float]:
        """
        检测哪些窗口达到极端值

        Returns:
            {窗口名: 百分位} 只包含 >= threshold 的窗口
        """
        if windows is None:
            windows = [7, 30, 90]
        percentiles = calculate_percentile_multi_window(value, history, windows)
        return {k: v for k, v in percentiles.items() if v is not None and v >= threshold}

    async def record_event(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
        value: float,
        percentile: float,
        price: float,
    ) -> int | None:
        """
        记录极端事件

        Returns:
            事件 ID，如果在冷却期内则返回 None
        """
        # 检查冷却期
        in_cooldown = await self.db.is_in_cooldown(
            symbol, dimension, window_days, self.cooldown_hours
        )
        if in_cooldown:
            return None

        event = ExtremeEvent(
            id=None,
            symbol=symbol,
            dimension=dimension,
            window_days=window_days,
            triggered_at=int(time.time() * 1000),
            value=value,
            percentile=percentile,
            price_at_trigger=price,
            price_4h=None,
            price_12h=None,
            price_24h=None,
            price_48h=None,
        )
        return await self.db.insert_extreme_event(event)
