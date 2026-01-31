# src/collector/indicator_fetcher.py
import logging
import time
from dataclasses import dataclass

from src.client.binance import BinanceClient
from src.storage.models import MarketIndicator, OISnapshot

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


@dataclass
class LongShortIndicators:
    """4 种多空比指标"""

    # 散户多空比
    global_long: float
    global_short: float
    global_ratio: float
    # 大户账户多空比
    top_account_long: float
    top_account_short: float
    top_account_ratio: float
    # 大户持仓多空比
    top_position_long: float
    top_position_short: float
    top_position_ratio: float
    # Taker 买卖比
    taker_buy: float
    taker_sell: float
    taker_ratio: float


class IndicatorFetcher:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self._client: BinanceClient | None = None

    async def init(self) -> None:
        """初始化持久化的 HTTP session"""
        self._client = BinanceClient()
        await self._client.__aenter__()

    async def close(self) -> None:
        """关闭 HTTP session"""
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

    def _get_client(self) -> BinanceClient:
        """获取 client，确保已初始化"""
        if self._client is None:
            raise RuntimeError("IndicatorFetcher not initialized. Call init() first.")
        return self._client

    def _to_ws_symbol(self, symbol: str) -> str:
        """转换 symbol 格式: BTC/USDT:USDT -> BTCUSDT"""
        return symbol.replace("/", "").replace(":USDT", "")

    async def fetch_all_oi(self) -> list[OISnapshot]:
        """获取所有币种的 OI"""
        results: list[OISnapshot] = []
        client = self._get_client()

        for symbol in self.symbols:
            try:
                ws_symbol = self._to_ws_symbol(symbol)
                oi = await client.get_open_interest(ws_symbol)
                klines = await client.get_klines(ws_symbol, "1h", limit=1)

                price = klines[0].close if klines else 0
                oi_usd = oi.open_interest * price

                results.append(
                    OISnapshot(
                        id=None,
                        exchange="binance",
                        symbol=symbol,
                        timestamp=oi.timestamp,
                        open_interest=oi.open_interest,
                        open_interest_usd=oi_usd,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to fetch OI for {symbol}: {e}")

        return results

    async def fetch_indicators(self, symbol: str) -> Indicators | None:
        """获取基础指标"""
        try:
            ws_symbol = self._to_ws_symbol(symbol)
            client = self._get_client()

            funding = await client.get_funding_rate(ws_symbol)
            klines = await client.get_klines(ws_symbol, "1h", limit=1)
            global_ls = await client.get_global_long_short_ratio(ws_symbol, "1h")

            price = klines[0].close if klines else 0

            return Indicators(
                funding_rate=funding.funding_rate * 100,  # 转为百分比
                long_short_ratio=global_ls.long_short_ratio,
                spot_price=price,  # 简化：使用期货价格
                futures_price=price,
            )
        except Exception as e:
            logger.error(f"Failed to fetch indicators for {symbol}: {e}")
            return None

    async def fetch_long_short_indicators(self, symbol: str) -> LongShortIndicators | None:
        """获取 4 种多空比指标"""
        try:
            ws_symbol = self._to_ws_symbol(symbol)
            client = self._get_client()

            global_ls = await client.get_global_long_short_ratio(ws_symbol, "1h")
            top_account = await client.get_top_long_short_account_ratio(ws_symbol, "1h")
            top_position = await client.get_top_long_short_position_ratio(ws_symbol, "1h")
            taker = await client.get_taker_long_short_ratio(ws_symbol, "1h")

            return LongShortIndicators(
                global_long=global_ls.long_ratio,
                global_short=global_ls.short_ratio,
                global_ratio=global_ls.long_short_ratio,
                top_account_long=top_account.long_ratio,
                top_account_short=top_account.short_ratio,
                top_account_ratio=top_account.long_short_ratio,
                top_position_long=top_position.long_ratio,
                top_position_short=top_position.short_ratio,
                top_position_ratio=top_position.long_short_ratio,
                taker_buy=taker.buy_vol,
                taker_sell=taker.sell_vol,
                taker_ratio=taker.buy_sell_ratio,
            )
        except Exception as e:
            logger.error(f"Failed to fetch long short indicators for {symbol}: {e}")
            return None

    async def fetch_market_indicators(self, symbol: str) -> MarketIndicator | None:
        """获取市场指标（用于洞察报告）"""
        try:
            ws_symbol = self._to_ws_symbol(symbol)
            client = self._get_client()

            top_account = await client.get_top_long_short_account_ratio(ws_symbol, "5m")
            top_position = await client.get_top_long_short_position_ratio(ws_symbol, "5m")
            global_account = await client.get_global_long_short_ratio(ws_symbol, "5m")
            taker = await client.get_taker_long_short_ratio(ws_symbol, "5m")

            return MarketIndicator(
                id=None,
                symbol=symbol,
                timestamp=int(time.time() * 1000),
                top_account_ratio=top_account.long_short_ratio,
                top_position_ratio=top_position.long_short_ratio,
                global_account_ratio=global_account.long_short_ratio,
                taker_buy_sell_ratio=taker.buy_sell_ratio,
            )
        except Exception as e:
            logger.error(f"Failed to fetch market indicators for {symbol}: {e}")
            return None

    async def fetch_open_interest(self, symbol: str) -> float:
        """获取持仓量"""
        ws_symbol = self._to_ws_symbol(symbol)
        client = self._get_client()
        oi = await client.get_open_interest(ws_symbol)
        return oi.open_interest
