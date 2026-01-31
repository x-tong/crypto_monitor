# src/collector/binance_trades.py
import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from src.client.binance import BinanceClient
from src.storage.models import Trade

from .base import BaseCollector

logger = logging.getLogger(__name__)


class BinanceTradesCollector(BaseCollector):
    def __init__(
        self,
        symbol: str,
        threshold_usd: float,
        on_trade: Callable[[Trade], Coroutine[Any, Any, None]],
    ):
        super().__init__(symbol)
        self.threshold_usd = threshold_usd
        self.on_trade = on_trade
        self._client = BinanceClient()

    async def connect(self) -> None:
        pass  # WebSocket 连接在 subscribe 时建立

    async def disconnect(self) -> None:
        pass  # WebSocket 连接在 subscribe 结束时关闭

    async def _process_message(self, message: Any) -> None:
        pass  # 不再使用，由 _handle_trade 处理

    async def _handle_trade(self, trade_data: dict[str, Any]) -> None:
        """处理交易数据"""
        value_usd = trade_data["price"] * trade_data["quantity"]
        if value_usd < self.threshold_usd:
            return

        trade = Trade(
            id=None,
            exchange="binance",
            symbol=self.symbol,
            timestamp=trade_data["timestamp"],
            price=trade_data["price"],
            amount=trade_data["quantity"],
            side=trade_data["side"],
            value_usd=value_usd,
        )
        await self.on_trade(trade)

    async def _run(self) -> None:
        # 转换 symbol 格式: BTC/USDT:USDT -> BTCUSDT
        ws_symbol = self.symbol.replace("/", "").replace(":USDT", "")

        while self.running:
            try:
                await self._client.subscribe_agg_trades(ws_symbol, self._handle_trade)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Binance trades error: {e}")
                await asyncio.sleep(5)
