# src/collector/event_backfiller.py
import logging
import time
from typing import TYPE_CHECKING

from src.storage.database import Database
from src.storage.models import ExtremeEvent

if TYPE_CHECKING:
    from src.client.binance import BinanceClient

logger = logging.getLogger(__name__)

# 时间偏移量 (ms)
BACKFILL_OFFSETS = {
    "price_4h": 4 * 3600 * 1000,
    "price_12h": 12 * 3600 * 1000,
    "price_24h": 24 * 3600 * 1000,
    "price_48h": 48 * 3600 * 1000,
}


class EventBackfiller:
    """极端事件后续价格回填"""

    def __init__(self, db: Database, client: "BinanceClient"):
        self.db = db
        self.client = client

    def _get_pending_fields(self, event: ExtremeEvent, now_ms: int) -> list[str]:
        """获取需要回填的字段"""
        pending = []
        for field, offset in BACKFILL_OFFSETS.items():
            current_value = getattr(event, field)
            if current_value is None and event.triggered_at + offset <= now_ms:
                pending.append(field)
        return pending

    async def _get_price_at(self, symbol: str, target_time_ms: int) -> float | None:
        """获取指定时间的价格"""
        try:
            # 将内部 symbol (BTC) 转换为 Binance symbol (BTCUSDT)
            binance_symbol = f"{symbol}USDT"
            klines = await self.client.get_klines(binance_symbol, "1h", limit=1)
            if klines:
                return klines[0].close
            return None
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
            return None

    async def backfill_one(self, event: ExtremeEvent, now_ms: int | None = None) -> int:
        """
        回填单个事件的后续价格

        Returns:
            回填的字段数量
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        pending_fields = self._get_pending_fields(event, now_ms)
        if not pending_fields:
            return 0

        filled_count = 0
        for field in pending_fields:
            offset = BACKFILL_OFFSETS[field]
            target_time = event.triggered_at + offset
            price = await self._get_price_at(event.symbol, target_time)

            if price is not None and event.id is not None:
                await self.db.update_extreme_event_price(event.id, field, price)
                filled_count += 1
                logger.info(f"Backfilled {field} for event {event.id}: {price}")

        return filled_count

    async def run(self) -> int:
        """
        运行回填任务

        Returns:
            回填的总字段数
        """
        events = await self.db.get_pending_backfill_events()
        total_filled = 0

        for event in events:
            filled = await self.backfill_one(event)
            total_filled += filled

        return total_filled
