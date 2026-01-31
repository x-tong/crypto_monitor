# src/collector/binance_liq.py
import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import websockets

from src.storage.models import Liquidation

from .base import BaseCollector

logger = logging.getLogger(__name__)

BINANCE_FUTURES_WS = "wss://fstream.binance.com/ws"


class BinanceLiquidationCollector(BaseCollector):
    SYMBOL_MAP = {
        "BTCUSDT": "BTC/USDT:USDT",
        "ETHUSDT": "ETH/USDT:USDT",
    }

    def __init__(
        self,
        symbols: list[str],
        on_liquidation: Callable[[Liquidation], Coroutine[Any, Any, None]],
    ):
        super().__init__("liquidations")
        self.symbols = symbols
        self.on_liquidation = on_liquidation
        self.ws: Any = None

    async def connect(self) -> None:
        streams = [
            f"{s.replace('/', '').replace(':USDT', '').lower()}@forceOrder" for s in self.symbols
        ]
        url = f"{BINANCE_FUTURES_WS}/{'/'.join(streams)}"
        self.ws = await websockets.connect(url)

    async def disconnect(self) -> None:
        if self.ws:
            await self.ws.close()

    def _parse_liquidation(self, data: dict[str, Any]) -> Liquidation | None:
        if data.get("e") != "forceOrder":
            return None

        order = data["o"]
        raw_symbol = order["s"]
        symbol = self.SYMBOL_MAP.get(raw_symbol)
        if not symbol:
            return None

        quantity = float(order["q"])
        avg_price = float(order["ap"])
        value_usd = quantity * avg_price

        return Liquidation(
            id=None,
            exchange="binance",
            symbol=symbol,
            timestamp=order["T"],
            side=order["S"].lower(),
            price=avg_price,
            quantity=quantity,
            value_usd=value_usd,
        )

    async def _process_message(self, message: str) -> None:
        try:
            data = json.loads(message)
            liq = self._parse_liquidation(data)
            if liq:
                await self.on_liquidation(liq)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse liquidation message: {message}")

    async def _run(self) -> None:
        await self.connect()
        assert self.ws is not None

        while self.running:
            try:
                message = await self.ws.recv()
                await self._process_message(message)
            except asyncio.CancelledError:
                break
            except websockets.ConnectionClosed:
                logger.warning("Binance liquidation WS disconnected, reconnecting...")
                await asyncio.sleep(5)
                await self.connect()
            except Exception as e:
                logger.error(f"Binance liquidation error: {e}")
                await asyncio.sleep(5)
