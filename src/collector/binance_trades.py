# src/collector/binance_trades.py
import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import ccxt.pro as ccxtpro

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
        self.exchange: ccxtpro.binanceusdm | None = None

    async def connect(self) -> None:
        self.exchange = ccxtpro.binanceusdm()

    async def disconnect(self) -> None:
        if self.exchange:
            await self.exchange.close()

    def _parse_trade(self, trade: dict[str, Any]) -> Trade | None:
        price = float(trade["price"])
        amount = float(trade["amount"])
        value_usd = price * amount

        if value_usd < self.threshold_usd:
            return None

        # 确定方向: m=True 表示卖方是 taker (sell), m=False 表示买方是 taker (buy)
        is_buyer_maker = trade.get("info", {}).get("m", True)
        side = "sell" if is_buyer_maker else "buy"

        return Trade(
            id=None,
            exchange="binance",
            symbol=trade["symbol"],
            timestamp=trade["timestamp"],
            price=price,
            amount=amount,
            side=side,
            value_usd=value_usd,
        )

    async def _process_message(self, trades: list[dict[str, Any]]) -> None:
        for trade_data in trades:
            trade = self._parse_trade(trade_data)
            if trade:
                await self.on_trade(trade)

    async def _run(self) -> None:
        await self.connect()
        assert self.exchange is not None

        while self.running:
            try:
                trades = await self.exchange.watch_trades(self.symbol)
                await self._process_message(trades)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Binance trades error: {e}")
                await asyncio.sleep(5)
