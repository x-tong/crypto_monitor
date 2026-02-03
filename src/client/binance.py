"""Binance Futures API 客户端"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import aiohttp

if TYPE_CHECKING:
    from src.client.models import (
        FundingRate,
        Kline,
        LongShortRatio,
        OpenInterest,
        TakerRatio,
    )

TradeCallback = Callable[[dict[str, Any]], Awaitable[None]]
LiquidationCallback = Callable[[dict[str, Any]], Awaitable[None]]


class BinanceAPIError(Exception):
    """Binance API 错误"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class BinanceClient:
    """Binance Futures API 客户端"""

    base_url: str = "https://fapi.binance.com"
    ws_url: str = "wss://fstream.binance.com"
    _session: aiohttp.ClientSession | None = field(default=None, repr=False)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """发送 HTTP 请求"""
        if self._session is None:
            raise RuntimeError("Session not initialized. Use 'async with' context.")

        url = f"{self.base_url}{endpoint}"

        if method == "GET":
            response = await self._session.get(url, params=params)
        else:
            response = await self._session.post(url, data=params)

        if response.status != 200:
            error_text = await response.text()
            try:
                error_data = json.loads(error_text)
                raise BinanceAPIError(error_data.get("code", -1), error_data.get("msg", error_text))
            except json.JSONDecodeError:
                raise BinanceAPIError(-1, error_text)

        return await response.json()

    async def init(self) -> None:
        """初始化 HTTP 会话"""
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        """关闭 HTTP 会话"""
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> BinanceClient:
        await self.init()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        """获取 K 线数据"""
        from src.client.models import Kline

        params: dict[str, str | int] = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        data = await self._request(
            "GET",
            "/fapi/v1/klines",
            params,
        )
        return [
            Kline(
                open_time=int(k[0]),
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
                close_time=int(k[6]),
            )
            for k in data
        ]

    async def get_open_interest(self, symbol: str) -> OpenInterest:
        """获取当前持仓量"""
        from src.client.models import OpenInterest

        data = await self._request("GET", "/fapi/v1/openInterest", {"symbol": symbol})
        return OpenInterest(
            symbol=data["symbol"],
            open_interest=float(data["openInterest"]),
            timestamp=int(data["time"]),
        )

    async def get_open_interest_hist(
        self,
        symbol: str,
        period: str,
        limit: int = 30,
    ) -> list[OpenInterest]:
        """获取历史持仓量"""
        from src.client.models import OpenInterest

        data = await self._request(
            "GET",
            "/futures/data/openInterestHist",
            {"symbol": symbol, "period": period, "limit": limit},
        )
        return [
            OpenInterest(
                symbol=d["symbol"],
                open_interest=float(d["sumOpenInterest"]),
                timestamp=int(d["timestamp"]),
            )
            for d in data
        ]

    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """获取当前资金费率"""
        from src.client.models import FundingRate

        data = await self._request("GET", "/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1})
        latest = data[0]
        return FundingRate(
            symbol=latest["symbol"],
            funding_rate=float(latest["fundingRate"]),
            funding_time=int(latest["fundingTime"]),
        )

    async def get_global_long_short_ratio(
        self,
        symbol: str,
        period: str,
        limit: int = 1,
    ) -> LongShortRatio:
        """获取散户多空比"""
        from src.client.models import LongShortRatio

        data = await self._request(
            "GET",
            "/futures/data/globalLongShortAccountRatio",
            {"symbol": symbol, "period": period, "limit": limit},
        )
        latest = data[0]
        return LongShortRatio(
            symbol=latest["symbol"],
            long_ratio=float(latest["longAccount"]),
            short_ratio=float(latest["shortAccount"]),
            long_short_ratio=float(latest["longShortRatio"]),
            timestamp=int(latest["timestamp"]),
        )

    async def get_top_long_short_account_ratio(
        self,
        symbol: str,
        period: str,
        limit: int = 1,
    ) -> LongShortRatio:
        """获取大户多空比（按账户数）"""
        from src.client.models import LongShortRatio

        data = await self._request(
            "GET",
            "/futures/data/topLongShortAccountRatio",
            {"symbol": symbol, "period": period, "limit": limit},
        )
        latest = data[0]
        return LongShortRatio(
            symbol=latest["symbol"],
            long_ratio=float(latest["longAccount"]),
            short_ratio=float(latest["shortAccount"]),
            long_short_ratio=float(latest["longShortRatio"]),
            timestamp=int(latest["timestamp"]),
        )

    async def get_top_long_short_position_ratio(
        self,
        symbol: str,
        period: str,
        limit: int = 1,
    ) -> LongShortRatio:
        """获取大户多空比（按持仓量）"""
        from src.client.models import LongShortRatio

        data = await self._request(
            "GET",
            "/futures/data/topLongShortPositionRatio",
            {"symbol": symbol, "period": period, "limit": limit},
        )
        latest = data[0]
        return LongShortRatio(
            symbol=latest["symbol"],
            long_ratio=float(latest["longAccount"]),
            short_ratio=float(latest["shortAccount"]),
            long_short_ratio=float(latest["longShortRatio"]),
            timestamp=int(latest["timestamp"]),
        )

    async def get_taker_long_short_ratio(
        self,
        symbol: str,
        period: str,
        limit: int = 1,
    ) -> TakerRatio:
        """获取 Taker 买卖比"""
        from src.client.models import TakerRatio

        data = await self._request(
            "GET",
            "/futures/data/takerlongshortRatio",
            {"symbol": symbol, "period": period, "limit": limit},
        )
        latest = data[0]
        return TakerRatio(
            symbol=symbol,  # API 不返回 symbol，使用请求参数
            buy_sell_ratio=float(latest["buySellRatio"]),
            buy_vol=float(latest["buyVol"]),
            sell_vol=float(latest["sellVol"]),
            timestamp=int(latest["timestamp"]),
        )

    async def _process_ws_message(
        self,
        message: str,
        callback: TradeCallback,
    ) -> None:
        """处理交易 WebSocket 消息"""
        data = json.loads(message)
        if data.get("e") != "aggTrade":
            return

        # m=True: buyer is maker (卖单成交) = sell
        # m=False: buyer is taker (买单成交) = buy
        side = "sell" if data["m"] else "buy"

        trade_data = {
            "symbol": data["s"],
            "price": float(data["p"]),
            "quantity": float(data["q"]),
            "timestamp": int(data["T"]),
            "side": side,
        }
        await callback(trade_data)

    async def _process_force_order_message(
        self,
        message: str,
        callback: LiquidationCallback,
    ) -> None:
        """处理爆仓 WebSocket 消息"""
        data = json.loads(message)
        if data.get("e") != "forceOrder":
            return

        order = data["o"]
        # S=SELL: 多头被强平 (卖出), S=BUY: 空头被强平 (买入)
        side = order["S"].lower()

        liq_data = {
            "symbol": order["s"],
            "side": side,
            "price": float(order["p"]),
            "quantity": float(order["q"]),
            "timestamp": int(order["T"]),
        }
        await callback(liq_data)

    async def subscribe_agg_trades(
        self,
        symbol: str,
        callback: TradeCallback,
    ) -> None:
        """订阅聚合交易流"""
        import websockets

        stream = f"{symbol.lower()}@aggTrade"
        url = f"{self.ws_url}/ws/{stream}"

        async with websockets.connect(url) as ws:
            async for message in ws:
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                await self._process_ws_message(message, callback)

    async def subscribe_force_order(
        self,
        callback: LiquidationCallback,
    ) -> None:
        """订阅全市场爆仓流"""
        import websockets

        url = f"{self.ws_url}/ws/!forceOrder@arr"

        async with websockets.connect(url) as ws:
            async for message in ws:
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                await self._process_force_order_message(message, callback)
