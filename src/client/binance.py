"""Binance Futures API 客户端"""

import json
from dataclasses import dataclass, field
from typing import Any

import aiohttp


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

    async def __aenter__(self) -> "BinanceClient":
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
    ) -> list["Kline"]:
        """获取 K 线数据"""
        from src.client.models import Kline

        data = await self._request(
            "GET",
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
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

    async def get_open_interest(self, symbol: str) -> "OpenInterest":
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
    ) -> list["OpenInterest"]:
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

    async def get_funding_rate(self, symbol: str) -> "FundingRate":
        """获取当前资金费率"""
        from src.client.models import FundingRate

        data = await self._request("GET", "/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1})
        latest = data[0]
        return FundingRate(
            symbol=latest["symbol"],
            funding_rate=float(latest["fundingRate"]),
            funding_time=int(latest["fundingTime"]),
        )
