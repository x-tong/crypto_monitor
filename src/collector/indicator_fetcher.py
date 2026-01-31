# src/collector/indicator_fetcher.py
import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import ccxt.async_support as ccxt

from src.storage.models import OISnapshot

logger = logging.getLogger(__name__)


@dataclass
class Indicators:
    funding_rate: float
    long_short_ratio: float
    spot_price: float
    futures_price: float

    @property
    def spot_perp_spread(self) -> float:
        if self.spot_price == 0:
            return 0.0
        return (self.futures_price - self.spot_price) / self.spot_price * 100


class IndicatorFetcher:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.binance: ccxt.binanceusdm | None = None
        self.binance_spot: ccxt.binance | None = None
        self.okx: ccxt.okx | None = None

    async def init(self) -> None:
        self.binance = ccxt.binanceusdm()
        self.binance_spot = ccxt.binance()
        self.okx = ccxt.okx()

    async def close(self) -> None:
        if self.binance:
            await self.binance.close()
        if self.binance_spot:
            await self.binance_spot.close()
        if self.okx:
            await self.okx.close()

    async def _fetch_oi(self, exchange: str, symbol: str) -> OISnapshot | None:
        try:
            ex = self.binance if exchange == "binance" else self.okx
            if not ex:
                return None

            data: dict[str, Any] = await ex.fetch_open_interest(symbol)

            oi_amount = data.get("openInterestAmount")
            oi_value = data.get("openInterestValue")
            timestamp = data.get("timestamp")

            if oi_amount is None or timestamp is None:
                logger.warning(
                    f"Incomplete OI data from {exchange} for {symbol}: "
                    f"amount={oi_amount}, ts={timestamp}"
                )
                return None

            # Calculate USD value from price if not provided (e.g., Binance)
            if oi_value is None:
                ticker: dict[str, Any] = await ex.fetch_ticker(symbol)
                price = ticker.get("last")
                if price is None:
                    logger.warning(f"Cannot get price to calculate OI value for {symbol}")
                    return None
                oi_value = oi_amount * price

            return OISnapshot(
                id=None,
                exchange=exchange,
                symbol=symbol,
                timestamp=timestamp,
                open_interest=oi_amount,
                open_interest_usd=oi_value,
            )
        except Exception as e:
            logger.error(f"Failed to fetch OI from {exchange}: {e}")
            return None

    async def fetch_all_oi(self) -> list[OISnapshot]:
        tasks = []
        for symbol in self.symbols:
            tasks.append(self._fetch_oi("binance", symbol))
            tasks.append(self._fetch_oi("okx", symbol))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, OISnapshot)]

    async def fetch_indicators(self, symbol: str) -> Indicators | None:
        try:
            assert self.binance is not None
            assert self.binance_spot is not None

            # Fetch funding rate
            funding: dict[str, Any] = await self.binance.fetch_funding_rate(symbol)
            funding_rate = funding.get("fundingRate", 0) * 100  # Convert to percentage

            # Fetch long/short ratio using history method (current ratio not supported)
            ls_history: list[dict[str, Any]] = await self.binance.fetch_long_short_ratio_history(
                symbol, "5m", limit=1
            )
            long_short_ratio = float(ls_history[-1]["longShortRatio"]) if ls_history else 1.0

            # Fetch spot price
            spot_ticker: dict[str, Any] = await self.binance_spot.fetch_ticker(
                symbol.replace(":USDT", "")
            )
            spot_price = spot_ticker["last"]

            # Fetch futures price
            futures_ticker: dict[str, Any] = await self.binance.fetch_ticker(symbol)
            futures_price = futures_ticker["last"]

            return Indicators(
                funding_rate=funding_rate,
                long_short_ratio=long_short_ratio,
                spot_price=spot_price,
                futures_price=futures_price,
            )
        except Exception as e:
            logger.error(f"Failed to fetch indicators for {symbol}: {e}")
            return None
