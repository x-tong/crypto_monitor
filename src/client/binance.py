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
