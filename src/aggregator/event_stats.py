# src/aggregator/event_stats.py
from typing import Any

from src.storage.database import Database


class EventStats:
    """极端事件历史统计"""

    def __init__(self, db: Database):
        self.db = db

    async def get_summary(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        获取历史事件统计摘要

        Returns:
            {
                "count": 事件数量,
                "stats": {
                    "4h": {"up_pct": 涨占比, "down_pct": 跌占比, "avg_change": 平均涨跌幅},
                    "12h": {...},
                    "24h": {...},
                    "48h": {...},
                },
            }
        """
        events = await self.db.get_extreme_events(
            symbol, dimension, window_days, limit=limit, completed_only=True
        )

        if not events:
            return {"count": 0, "stats": {}}

        stats: dict[str, dict[str, float]] = {}
        for period, field in [
            ("4h", "price_4h"),
            ("12h", "price_12h"),
            ("24h", "price_24h"),
            ("48h", "price_48h"),
        ]:
            changes = []
            for e in events:
                price_after = getattr(e, field)
                if price_after is not None and e.price_at_trigger > 0:
                    change = (price_after - e.price_at_trigger) / e.price_at_trigger * 100
                    changes.append(change)

            if changes:
                up_count = sum(1 for c in changes if c > 0)
                down_count = sum(1 for c in changes if c < 0)
                total = len(changes)
                stats[period] = {
                    "up_pct": round(up_count / total * 100, 1),
                    "down_pct": round(down_count / total * 100, 1),
                    "avg_change": round(sum(changes) / total, 2),
                }

        return {"count": len(events), "stats": stats}

    async def get_latest_event(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
    ) -> dict[str, Any] | None:
        """获取最近一次完整事件"""
        events = await self.db.get_extreme_events(
            symbol, dimension, window_days, limit=1, completed_only=True
        )
        if not events:
            return None

        e = events[0]
        change_24h = None
        if e.price_24h is not None and e.price_at_trigger > 0:
            change_24h = round(
                (e.price_24h - e.price_at_trigger) / e.price_at_trigger * 100, 2
            )

        return {
            "triggered_at": e.triggered_at,
            "price_at_trigger": e.price_at_trigger,
            "price_24h": e.price_24h,
            "change_24h": change_24h,
        }
