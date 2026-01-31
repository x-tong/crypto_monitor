# Binance 专注重构实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 精简系统到只做 Binance，去掉 ccxt，新增多空比数据，实现分级告警。

**Architecture:** 新建 `src/client/binance.py` 封装所有 Binance API，替代 ccxt。修改 `trigger.py` 实现分级告警（观察/重要）。删除所有 OKX 相关代码。

**Tech Stack:** aiohttp (HTTP), websockets (WS), aiosqlite, pydantic

---

## Phase 1: Binance Client 基础封装

### Task 1.1: 创建 BinanceClient 基础结构

**Files:**
- Create: `src/client/__init__.py`
- Create: `src/client/binance.py`
- Create: `tests/client/__init__.py`
- Create: `tests/client/test_binance.py`

**Step 1: 创建目录和空文件**

```bash
mkdir -p src/client tests/client
touch src/client/__init__.py tests/client/__init__.py
```

**Step 2: 写失败测试 - BinanceClient 初始化**

`tests/client/test_binance.py`:
```python
import pytest
from src.client.binance import BinanceClient


def test_binance_client_init():
    client = BinanceClient()
    assert client.base_url == "https://fapi.binance.com"
    assert client.ws_url == "wss://fstream.binance.com"


def test_binance_client_custom_urls():
    client = BinanceClient(
        base_url="https://custom.api.com",
        ws_url="wss://custom.ws.com",
    )
    assert client.base_url == "https://custom.api.com"
    assert client.ws_url == "wss://custom.ws.com"
```

**Step 3: 运行测试验证失败**

```bash
uv run pytest tests/client/test_binance.py -v
```
Expected: FAIL - `ModuleNotFoundError: No module named 'src.client.binance'`

**Step 4: 实现 BinanceClient 基础结构**

`src/client/binance.py`:
```python
"""Binance Futures API 客户端"""

from dataclasses import dataclass


@dataclass
class BinanceClient:
    """Binance Futures API 客户端"""

    base_url: str = "https://fapi.binance.com"
    ws_url: str = "wss://fstream.binance.com"
```

**Step 5: 运行测试验证通过**

```bash
uv run pytest tests/client/test_binance.py -v
```
Expected: PASS

**Step 6: 提交**

```bash
git add src/client/ tests/client/
git commit -m "feat: 添加 BinanceClient 基础结构"
```

---

### Task 1.2: 添加 HTTP 请求方法

**Files:**
- Modify: `src/client/binance.py`
- Modify: `tests/client/test_binance.py`

**Step 1: 写失败测试 - _request 方法**

追加到 `tests/client/test_binance.py`:
```python
import aiohttp
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_request_get():
    client = BinanceClient()

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"symbol": "BTCUSDT"})

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with aiohttp.ClientSession() as session:
            client._session = session
            result = await client._request("GET", "/fapi/v1/ticker/price", {"symbol": "BTCUSDT"})
            assert result == {"symbol": "BTCUSDT"}


@pytest.mark.asyncio
async def test_request_handles_error():
    client = BinanceClient()

    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"code": -1121, "msg": "Invalid symbol"}')

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with aiohttp.ClientSession() as session:
            client._session = session
            with pytest.raises(Exception, match="Invalid symbol"):
                await client._request("GET", "/fapi/v1/ticker/price", {"symbol": "INVALID"})
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/client/test_binance.py::test_request_get -v
```
Expected: FAIL - `AttributeError: 'BinanceClient' object has no attribute '_request'`

**Step 3: 实现 _request 方法**

更新 `src/client/binance.py`:
```python
"""Binance Futures API 客户端"""

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
            import json

            try:
                error_data = json.loads(error_text)
                raise BinanceAPIError(error_data.get("code", -1), error_data.get("msg", error_text))
            except json.JSONDecodeError:
                raise BinanceAPIError(-1, error_text)

        return await response.json()

    async def __aenter__(self) -> "BinanceClient":
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session:
            await self._session.close()
            self._session = None
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/client/test_binance.py -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add src/client/binance.py tests/client/test_binance.py
git commit -m "feat: BinanceClient 添加 HTTP 请求方法"
```

---

### Task 1.3: 添加 K 线和价格接口

**Files:**
- Modify: `src/client/binance.py`
- Modify: `tests/client/test_binance.py`
- Create: `src/client/models.py`

**Step 1: 创建数据模型**

`src/client/models.py`:
```python
"""Binance API 数据模型"""

from dataclasses import dataclass


@dataclass
class Kline:
    """K 线数据"""

    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int


@dataclass
class OpenInterest:
    """持仓量数据"""

    symbol: str
    open_interest: float
    timestamp: int


@dataclass
class FundingRate:
    """资金费率数据"""

    symbol: str
    funding_rate: float
    funding_time: int


@dataclass
class LongShortRatio:
    """多空比数据"""

    symbol: str
    long_ratio: float
    short_ratio: float
    long_short_ratio: float
    timestamp: int


@dataclass
class TakerRatio:
    """Taker 买卖比数据"""

    symbol: str
    buy_sell_ratio: float
    buy_vol: float
    sell_vol: float
    timestamp: int
```

**Step 2: 写失败测试 - get_klines**

追加到 `tests/client/test_binance.py`:
```python
from src.client.models import Kline


@pytest.mark.asyncio
async def test_get_klines():
    client = BinanceClient()

    mock_data = [
        [1704067200000, "42000.0", "42500.0", "41800.0", "42300.0", "1000.0", 1704070799999]
    ]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with client:
            klines = await client.get_klines("BTCUSDT", "1h", limit=1)
            assert len(klines) == 1
            assert isinstance(klines[0], Kline)
            assert klines[0].close == 42300.0
```

**Step 3: 运行测试验证失败**

```bash
uv run pytest tests/client/test_binance.py::test_get_klines -v
```
Expected: FAIL - `AttributeError: 'BinanceClient' object has no attribute 'get_klines'`

**Step 4: 实现 get_klines**

追加到 `src/client/binance.py`:
```python
from src.client.models import Kline

# 在 BinanceClient 类中添加:

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
    ) -> list[Kline]:
        """获取 K 线数据"""
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
```

**Step 5: 运行测试验证通过**

```bash
uv run pytest tests/client/test_binance.py::test_get_klines -v
```
Expected: PASS

**Step 6: 提交**

```bash
git add src/client/
git commit -m "feat: BinanceClient 添加 K 线接口"
```

---

### Task 1.4: 添加持仓量接口

**Files:**
- Modify: `src/client/binance.py`
- Modify: `tests/client/test_binance.py`

**Step 1: 写失败测试 - get_open_interest**

追加到 `tests/client/test_binance.py`:
```python
from src.client.models import OpenInterest


@pytest.mark.asyncio
async def test_get_open_interest():
    client = BinanceClient()

    mock_data = {"symbol": "BTCUSDT", "openInterest": "50000.123", "time": 1704067200000}
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with client:
            oi = await client.get_open_interest("BTCUSDT")
            assert isinstance(oi, OpenInterest)
            assert oi.symbol == "BTCUSDT"
            assert oi.open_interest == 50000.123


@pytest.mark.asyncio
async def test_get_open_interest_hist():
    client = BinanceClient()

    mock_data = [
        {"symbol": "BTCUSDT", "sumOpenInterest": "50000.0", "timestamp": 1704067200000},
        {"symbol": "BTCUSDT", "sumOpenInterest": "51000.0", "timestamp": 1704070800000},
    ]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with client:
            oi_list = await client.get_open_interest_hist("BTCUSDT", "1h", limit=2)
            assert len(oi_list) == 2
            assert oi_list[0].open_interest == 50000.0
            assert oi_list[1].open_interest == 51000.0
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/client/test_binance.py::test_get_open_interest -v
```
Expected: FAIL

**Step 3: 实现 get_open_interest 和 get_open_interest_hist**

追加到 `src/client/binance.py` 的 BinanceClient 类:
```python
from src.client.models import Kline, OpenInterest

    async def get_open_interest(self, symbol: str) -> OpenInterest:
        """获取当前持仓量"""
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
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/client/test_binance.py::test_get_open_interest tests/client/test_binance.py::test_get_open_interest_hist -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add src/client/binance.py tests/client/test_binance.py
git commit -m "feat: BinanceClient 添加持仓量接口"
```

---

### Task 1.5: 添加资金费率接口

**Files:**
- Modify: `src/client/binance.py`
- Modify: `tests/client/test_binance.py`

**Step 1: 写失败测试**

追加到 `tests/client/test_binance.py`:
```python
from src.client.models import FundingRate


@pytest.mark.asyncio
async def test_get_funding_rate():
    client = BinanceClient()

    mock_data = [{"symbol": "BTCUSDT", "fundingRate": "0.0001", "fundingTime": 1704067200000}]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with client:
            fr = await client.get_funding_rate("BTCUSDT")
            assert isinstance(fr, FundingRate)
            assert fr.funding_rate == 0.0001
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/client/test_binance.py::test_get_funding_rate -v
```
Expected: FAIL

**Step 3: 实现 get_funding_rate**

追加到 `src/client/binance.py`:
```python
from src.client.models import Kline, OpenInterest, FundingRate

    async def get_funding_rate(self, symbol: str) -> FundingRate:
        """获取当前资金费率"""
        data = await self._request("GET", "/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1})
        latest = data[0]
        return FundingRate(
            symbol=latest["symbol"],
            funding_rate=float(latest["fundingRate"]),
            funding_time=int(latest["fundingTime"]),
        )
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/client/test_binance.py::test_get_funding_rate -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add src/client/binance.py tests/client/test_binance.py
git commit -m "feat: BinanceClient 添加资金费率接口"
```

---

### Task 1.6: 添加多空比接口（4 个端点）

**Files:**
- Modify: `src/client/binance.py`
- Modify: `tests/client/test_binance.py`

**Step 1: 写失败测试 - 4 个多空比接口**

追加到 `tests/client/test_binance.py`:
```python
from src.client.models import LongShortRatio, TakerRatio


@pytest.mark.asyncio
async def test_get_global_long_short_ratio():
    client = BinanceClient()

    mock_data = [
        {"symbol": "BTCUSDT", "longAccount": "0.55", "shortAccount": "0.45", "longShortRatio": "1.22", "timestamp": 1704067200000}
    ]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with client:
            ratio = await client.get_global_long_short_ratio("BTCUSDT", "1h")
            assert isinstance(ratio, LongShortRatio)
            assert ratio.long_ratio == 0.55
            assert ratio.short_ratio == 0.45
            assert ratio.long_short_ratio == 1.22


@pytest.mark.asyncio
async def test_get_top_long_short_account_ratio():
    client = BinanceClient()

    mock_data = [
        {"symbol": "BTCUSDT", "longAccount": "0.60", "shortAccount": "0.40", "longShortRatio": "1.50", "timestamp": 1704067200000}
    ]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with client:
            ratio = await client.get_top_long_short_account_ratio("BTCUSDT", "1h")
            assert ratio.long_ratio == 0.60


@pytest.mark.asyncio
async def test_get_top_long_short_position_ratio():
    client = BinanceClient()

    mock_data = [
        {"symbol": "BTCUSDT", "longAccount": "0.65", "shortAccount": "0.35", "longShortRatio": "1.86", "timestamp": 1704067200000}
    ]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with client:
            ratio = await client.get_top_long_short_position_ratio("BTCUSDT", "1h")
            assert ratio.long_ratio == 0.65


@pytest.mark.asyncio
async def test_get_taker_long_short_ratio():
    client = BinanceClient()

    mock_data = [
        {"symbol": "BTCUSDT", "buySellRatio": "1.10", "buyVol": "5000.0", "sellVol": "4545.45", "timestamp": 1704067200000}
    ]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    with patch("aiohttp.ClientSession.get", return_value=mock_response):
        async with client:
            ratio = await client.get_taker_long_short_ratio("BTCUSDT", "1h")
            assert isinstance(ratio, TakerRatio)
            assert ratio.buy_sell_ratio == 1.10
            assert ratio.buy_vol == 5000.0
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/client/test_binance.py -k "long_short" -v
```
Expected: FAIL

**Step 3: 实现 4 个多空比接口**

追加到 `src/client/binance.py`:
```python
from src.client.models import Kline, OpenInterest, FundingRate, LongShortRatio, TakerRatio

    async def get_global_long_short_ratio(
        self,
        symbol: str,
        period: str,
        limit: int = 1,
    ) -> LongShortRatio:
        """获取散户多空比"""
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
        data = await self._request(
            "GET",
            "/futures/data/takerlongshortRatio",
            {"symbol": symbol, "period": period, "limit": limit},
        )
        latest = data[0]
        return TakerRatio(
            symbol=latest["symbol"],
            buy_sell_ratio=float(latest["buySellRatio"]),
            buy_vol=float(latest["buyVol"]),
            sell_vol=float(latest["sellVol"]),
            timestamp=int(latest["timestamp"]),
        )
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/client/test_binance.py -k "long_short" -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add src/client/binance.py tests/client/test_binance.py
git commit -m "feat: BinanceClient 添加 4 个多空比接口"
```

---

### Task 1.7: 添加 WebSocket 订阅（交易和爆仓）

**Files:**
- Modify: `src/client/binance.py`
- Create: `tests/client/test_binance_ws.py`

**Step 1: 写失败测试 - WebSocket 订阅**

`tests/client/test_binance_ws.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.client.binance import BinanceClient


@pytest.mark.asyncio
async def test_subscribe_agg_trades():
    client = BinanceClient()

    mock_ws = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock()
    mock_ws.__aiter__ = lambda self: self

    messages = [
        json.dumps({
            "e": "aggTrade",
            "s": "BTCUSDT",
            "p": "42000.0",
            "q": "1.5",
            "T": 1704067200000,
            "m": False,  # buyer is maker = False means taker buy
        })
    ]
    mock_ws.__anext__ = AsyncMock(side_effect=messages + [StopAsyncIteration()])

    received = []

    async def callback(trade_data):
        received.append(trade_data)

    with patch("websockets.connect", return_value=mock_ws):
        # 只运行一次迭代
        await client._process_ws_message(messages[0], callback)

    assert len(received) == 1
    assert received[0]["symbol"] == "BTCUSDT"
    assert received[0]["price"] == 42000.0
    assert received[0]["side"] == "buy"


@pytest.mark.asyncio
async def test_subscribe_force_order():
    client = BinanceClient()

    message = json.dumps({
        "e": "forceOrder",
        "o": {
            "s": "BTCUSDT",
            "S": "SELL",  # SELL = 多头爆仓
            "p": "41000.0",
            "q": "2.0",
            "T": 1704067200000,
        }
    })

    received = []

    async def callback(liq_data):
        received.append(liq_data)

    await client._process_force_order_message(message, callback)

    assert len(received) == 1
    assert received[0]["symbol"] == "BTCUSDT"
    assert received[0]["side"] == "sell"  # 多头爆仓
    assert received[0]["price"] == 41000.0
    assert received[0]["quantity"] == 2.0
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/client/test_binance_ws.py -v
```
Expected: FAIL

**Step 3: 实现 WebSocket 处理方法**

追加到 `src/client/binance.py`:
```python
import json
from typing import Callable, Awaitable

TradeCallback = Callable[[dict], Awaitable[None]]
LiquidationCallback = Callable[[dict], Awaitable[None]]

# 在 BinanceClient 类中添加:

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
                await self._process_force_order_message(message, callback)
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/client/test_binance_ws.py -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add src/client/binance.py tests/client/test_binance_ws.py
git commit -m "feat: BinanceClient 添加 WebSocket 订阅"
```

---

## Phase 2: 数据库变更

### Task 2.1: 添加 long_short_snapshots 表

**Files:**
- Modify: `src/storage/database.py`
- Modify: `tests/storage/test_database.py`

**Step 1: 写失败测试**

追加到 `tests/storage/test_database.py`:
```python
@pytest.mark.asyncio
async def test_insert_and_get_long_short_snapshot(db):
    await db.insert_long_short_snapshot(
        symbol="BTCUSDT",
        timestamp=1704067200000,
        ratio_type="global",
        long_ratio=0.55,
        short_ratio=0.45,
        long_short_ratio=1.22,
    )

    snapshots = await db.get_long_short_snapshots("BTCUSDT", "global", hours=1)
    assert len(snapshots) == 1
    assert snapshots[0]["long_ratio"] == 0.55
    assert snapshots[0]["ratio_type"] == "global"


@pytest.mark.asyncio
async def test_get_latest_long_short_snapshot(db):
    await db.insert_long_short_snapshot(
        symbol="BTCUSDT",
        timestamp=1704067200000,
        ratio_type="top_position",
        long_ratio=0.60,
        short_ratio=0.40,
        long_short_ratio=1.50,
    )
    await db.insert_long_short_snapshot(
        symbol="BTCUSDT",
        timestamp=1704070800000,
        ratio_type="top_position",
        long_ratio=0.65,
        short_ratio=0.35,
        long_short_ratio=1.86,
    )

    latest = await db.get_latest_long_short_snapshot("BTCUSDT", "top_position")
    assert latest is not None
    assert latest["long_ratio"] == 0.65
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/storage/test_database.py::test_insert_and_get_long_short_snapshot -v
```
Expected: FAIL

**Step 3: 实现表和方法**

在 `src/storage/database.py` 的 `_create_tables` 方法中添加:
```python
            CREATE TABLE IF NOT EXISTS long_short_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                ratio_type TEXT NOT NULL,
                long_ratio REAL NOT NULL,
                short_ratio REAL NOT NULL,
                long_short_ratio REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_ls_symbol_type_time
                ON long_short_snapshots(symbol, ratio_type, timestamp);
```

在 `Database` 类中添加方法:
```python
    async def insert_long_short_snapshot(
        self,
        symbol: str,
        timestamp: int,
        ratio_type: str,
        long_ratio: float,
        short_ratio: float,
        long_short_ratio: float,
    ) -> None:
        """插入多空比快照"""
        async with self._get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO long_short_snapshots
                (symbol, timestamp, ratio_type, long_ratio, short_ratio, long_short_ratio)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (symbol, timestamp, ratio_type, long_ratio, short_ratio, long_short_ratio),
            )
            await conn.commit()

    async def get_long_short_snapshots(
        self,
        symbol: str,
        ratio_type: str,
        hours: int = 24,
    ) -> list[dict]:
        """获取多空比快照历史"""
        import time

        cutoff = int(time.time() * 1000) - hours * 3600 * 1000
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM long_short_snapshots
                WHERE symbol = ? AND ratio_type = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (symbol, ratio_type, cutoff),
            )
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def get_latest_long_short_snapshot(
        self,
        symbol: str,
        ratio_type: str,
    ) -> dict | None:
        """获取最新多空比快照"""
        async with self._get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM long_short_snapshots
                WHERE symbol = ? AND ratio_type = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (symbol, ratio_type),
            )
            row = await cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/storage/test_database.py -k "long_short" -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add src/storage/database.py tests/storage/test_database.py
git commit -m "feat: 添加 long_short_snapshots 表"
```

---

## Phase 3: 删除 OKX 和 ccxt

### Task 3.1: 删除 OKX 相关代码

**Files:**
- Delete: `src/collector/okx_trades.py`
- Delete: `tests/collector/test_okx_trades.py`
- Modify: `src/main.py` (移除 OKX collector)
- Modify: `src/config.py` (移除 OKX 配置)

**Step 1: 删除文件**

```bash
rm src/collector/okx_trades.py tests/collector/test_okx_trades.py
```

**Step 2: 修改 config.py**

从 `ExchangesConfig` 中移除 `okx` 字段:
```python
@dataclass
class ExchangesConfig:
    binance: ExchangeConfig = field(default_factory=ExchangeConfig)
    # 删除: okx: ExchangeConfig = field(default_factory=ExchangeConfig)
```

**Step 3: 修改 main.py**

移除 OKX collector 创建逻辑，搜索 `OKXTradesCollector` 并删除相关代码。

**Step 4: 运行测试确保没有 OKX 引用**

```bash
uv run pytest tests/ -v
```
Expected: PASS (无 OKX 相关错误)

**Step 5: 提交**

```bash
git add -A
git commit -m "refactor: 移除 OKX 相关代码"
```

---

### Task 3.2: 删除 ccxt 依赖

**Files:**
- Modify: `pyproject.toml`
- Delete: `src/collector/binance_trades.py` (ccxt 版本)
- Create: `src/collector/binance_trades.py` (新版本，使用 BinanceClient)

**Step 1: 修改 pyproject.toml**

移除 ccxt 依赖，添加 aiohttp:
```toml
dependencies = [
    # 删除: "ccxt>=4.0.0",
    "aiohttp>=3.9.0",
    "websockets>=12.0",
    # ... 其他依赖保持不变
]
```

**Step 2: 更新依赖**

```bash
uv sync
```

**Step 3: 重写 binance_trades.py**

`src/collector/binance_trades.py`:
```python
"""Binance 交易采集器（使用自封装 API）"""

from src.collector.base import BaseCollector
from src.client.binance import BinanceClient
from src.storage.models import Trade


class BinanceTradesCollector(BaseCollector):
    """Binance 大单交易采集器"""

    def __init__(
        self,
        symbol: str,
        min_value_usd: float = 100000,
        on_trade=None,
    ):
        super().__init__(symbol)
        self.min_value_usd = min_value_usd
        self.on_trade = on_trade
        self._client = BinanceClient()
        self._running = False

    async def _run(self) -> None:
        """运行采集"""
        self._running = True

        async def handle_trade(trade_data: dict):
            value_usd = trade_data["price"] * trade_data["quantity"]
            if value_usd < self.min_value_usd:
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
            if self.on_trade:
                await self.on_trade(trade)

        # 转换 symbol 格式: BTC/USDT:USDT -> BTCUSDT
        ws_symbol = self.symbol.replace("/", "").replace(":USDT", "")
        await self._client.subscribe_agg_trades(ws_symbol, handle_trade)

    async def stop(self) -> None:
        """停止采集"""
        self._running = False
```

**Step 4: 更新测试**

`tests/collector/test_binance_trades.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch

from src.collector.binance_trades import BinanceTradesCollector
from src.storage.models import Trade


@pytest.mark.asyncio
async def test_binance_trades_collector_filters_small_trades():
    collector = BinanceTradesCollector(
        symbol="BTC/USDT:USDT",
        min_value_usd=100000,
    )

    received = []

    async def on_trade(trade: Trade):
        received.append(trade)

    collector.on_trade = on_trade

    # 小单 (42000 * 1 = 42000 < 100000)
    small_trade = {
        "symbol": "BTCUSDT",
        "price": 42000.0,
        "quantity": 1.0,
        "timestamp": 1704067200000,
        "side": "buy",
    }

    # 大单 (42000 * 3 = 126000 > 100000)
    large_trade = {
        "symbol": "BTCUSDT",
        "price": 42000.0,
        "quantity": 3.0,
        "timestamp": 1704067200000,
        "side": "buy",
    }

    # 模拟处理
    async def handle_trade(trade_data):
        value_usd = trade_data["price"] * trade_data["quantity"]
        if value_usd < collector.min_value_usd:
            return
        trade = Trade(
            id=None,
            exchange="binance",
            symbol=collector.symbol,
            timestamp=trade_data["timestamp"],
            price=trade_data["price"],
            amount=trade_data["quantity"],
            side=trade_data["side"],
            value_usd=value_usd,
        )
        await on_trade(trade)

    await handle_trade(small_trade)
    await handle_trade(large_trade)

    assert len(received) == 1
    assert received[0].value_usd == 126000.0
```

**Step 5: 运行测试**

```bash
uv run pytest tests/collector/test_binance_trades.py -v
```
Expected: PASS

**Step 6: 提交**

```bash
git add -A
git commit -m "refactor: 移除 ccxt，使用自封装 BinanceClient"
```

---

## Phase 4: 分级告警

### Task 4.1: 添加分级告警类型

**Files:**
- Modify: `src/alert/trigger.py`
- Modify: `tests/alert/test_trigger.py`

**Step 1: 写失败测试**

追加到 `tests/alert/test_trigger.py`:
```python
from src.alert.trigger import AlertLevel, check_tiered_alerts


def test_observe_alert_single_dimension():
    """单维度极端触发观察提醒"""
    percentiles = {
        "flow": 92,  # > 90
        "oi_change": 60,
        "liquidation": 70,
        "funding_rate": 50,
        "global_ls": 65,
        "top_position_ls": 55,
        "taker_ratio": 45,
    }

    alerts = check_tiered_alerts(percentiles, threshold=90, min_dimensions=3)

    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.OBSERVE
    assert "flow" in [d[0] for d in alerts[0].dimensions]


def test_important_alert_multi_dimension():
    """多维度极端触发重要提醒"""
    percentiles = {
        "flow": 95,
        "oi_change": 92,
        "liquidation": 94,
        "funding_rate": 50,
        "global_ls": 65,
        "top_position_ls": 55,
        "taker_ratio": 45,
    }

    alerts = check_tiered_alerts(percentiles, threshold=90, min_dimensions=3)

    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.IMPORTANT
    assert len(alerts[0].dimensions) == 3


def test_no_alert_when_all_normal():
    """无极端维度时不触发"""
    percentiles = {
        "flow": 60,
        "oi_change": 50,
        "liquidation": 70,
        "funding_rate": 50,
        "global_ls": 65,
        "top_position_ls": 55,
        "taker_ratio": 45,
    }

    alerts = check_tiered_alerts(percentiles, threshold=90, min_dimensions=3)
    assert len(alerts) == 0
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/alert/test_trigger.py::test_observe_alert_single_dimension -v
```
Expected: FAIL

**Step 3: 实现分级告警**

更新 `src/alert/trigger.py`:
```python
from dataclasses import dataclass
from enum import Enum


class AlertLevel(Enum):
    OBSERVE = "observe"
    IMPORTANT = "important"


@dataclass
class TieredAlert:
    level: AlertLevel
    dimensions: list[tuple[str, float]]  # [(维度名, 百分位), ...]


def check_tiered_alerts(
    percentiles: dict[str, float],
    threshold: float = 90,
    min_dimensions: int = 3,
) -> list[TieredAlert]:
    """检查分级告警

    Args:
        percentiles: 各维度的百分位 {维度名: 百分位}
        threshold: 极端阈值 (默认 P90)
        min_dimensions: 触发重要提醒的最少维度数

    Returns:
        告警列表
    """
    extreme = [(name, p) for name, p in percentiles.items() if p > threshold]

    if not extreme:
        return []

    if len(extreme) >= min_dimensions:
        return [TieredAlert(level=AlertLevel.IMPORTANT, dimensions=extreme)]
    else:
        return [TieredAlert(level=AlertLevel.OBSERVE, dimensions=extreme)]
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/alert/test_trigger.py -k "tiered" -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add src/alert/trigger.py tests/alert/test_trigger.py
git commit -m "feat: 添加分级告警（观察/重要）"
```

---

### Task 4.2: 添加分级告警消息格式

**Files:**
- Modify: `src/notifier/formatter.py`
- Modify: `tests/notifier/test_formatter.py`

**Step 1: 写失败测试**

追加到 `tests/notifier/test_formatter.py`:
```python
from src.notifier.formatter import format_observe_alert, format_important_alert


def test_format_observe_alert():
    data = {
        "symbol": "BTC",
        "price": 103850,
        "price_change_1h": -0.5,
        "dimensions": [("主力资金", 92, "-$8.2M")],
        "timestamp": "2026-01-30 14:32 UTC",
    }

    result = format_observe_alert(data)
    assert "📢 BTC 观察提醒" in result
    assert "主力资金" in result
    assert "🔴 P92" in result
    assert "-$8.2M" in result


def test_format_important_alert():
    data = {
        "symbol": "BTC",
        "price": 101200,
        "price_change_1h": -2.8,
        "dimensions": [
            ("主力资金", 96, "-$15.2M"),
            ("OI变化", 94, "+4.2%"),
            ("爆仓", 95, "$35M"),
        ],
        "timestamp": "2026-01-30 14:32 UTC",
    }

    result = format_important_alert(data)
    assert "🚨 BTC 重要提醒" in result
    assert "3 维度共振" in result
    assert "主力资金" in result
    assert "OI变化" in result
    assert "爆仓" in result
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/notifier/test_formatter.py -k "alert" -v
```
Expected: FAIL

**Step 3: 实现消息格式化**

追加到 `src/notifier/formatter.py`:
```python
def format_observe_alert(data: dict) -> str:
    """格式化观察提醒"""
    lines = [
        f"📢 {data['symbol']} 观察提醒",
        "",
    ]

    for name, percentile, value in data["dimensions"]:
        lines.append(f"{name}: {value} 🔴 P{int(percentile)}")

    lines.extend([
        "",
        f"💵 ${data['price']:,.0f} ({data['price_change_1h']:+.1f}% 1h)",
        f"⏰ {data['timestamp']}",
    ])

    return "\n".join(lines)


def format_important_alert(data: dict) -> str:
    """格式化重要提醒"""
    dim_count = len(data["dimensions"])
    lines = [
        f"🚨 {data['symbol']} 重要提醒 - {dim_count} 维度共振",
        "",
    ]

    for name, percentile, value in data["dimensions"]:
        lines.append(f"• {name}: {value} 🔴 P{int(percentile)}")

    lines.extend([
        "",
        f"💵 ${data['price']:,.0f} ({data['price_change_1h']:+.1f}% 1h)",
        f"⏰ {data['timestamp']}",
    ])

    return "\n".join(lines)
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/notifier/test_formatter.py -k "alert" -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add src/notifier/formatter.py tests/notifier/test_formatter.py
git commit -m "feat: 添加观察/重要提醒消息格式"
```

---

## Phase 5: 集成和配置更新

### Task 5.1: 更新配置结构

**Files:**
- Modify: `src/config.py`
- Modify: `tests/test_config.py`
- Modify: `config.example.yaml`

**Step 1: 写失败测试**

追加到 `tests/test_config.py`:
```python
def test_tiered_alerts_config():
    config = load_config(Path("config.example.yaml"))

    assert config.alerts.observe.enabled is True
    assert config.alerts.observe.percentile_threshold == 90
    assert config.alerts.important.enabled is True
    assert config.alerts.important.min_dimensions == 3


def test_long_short_ratio_config():
    config = load_config(Path("config.example.yaml"))

    assert "15m" in config.long_short_ratio.periods
    assert "1h" in config.long_short_ratio.periods
    assert config.long_short_ratio.fetch_interval_minutes == 5
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_config.py -k "tiered" -v
```
Expected: FAIL

**Step 3: 更新配置模型**

更新 `src/config.py`:
```python
@dataclass
class ObserveAlertConfig:
    enabled: bool = True
    percentile_threshold: int = 90


@dataclass
class ImportantAlertConfig:
    enabled: bool = True
    percentile_threshold: int = 90
    min_dimensions: int = 3


@dataclass
class LongShortRatioConfig:
    periods: list[str] = field(default_factory=lambda: ["15m", "1h"])
    fetch_interval_minutes: int = 5


# 更新 AlertsConfig
@dataclass
class AlertsConfig:
    whale_flow: AlertConfig = field(default_factory=AlertConfig)
    oi_change: AlertConfig = field(default_factory=AlertConfig)
    liquidation: AlertConfig = field(default_factory=AlertConfig)
    observe: ObserveAlertConfig = field(default_factory=ObserveAlertConfig)
    important: ImportantAlertConfig = field(default_factory=ImportantAlertConfig)


# 更新 Config
@dataclass
class Config:
    # ... 现有字段 ...
    long_short_ratio: LongShortRatioConfig = field(default_factory=LongShortRatioConfig)
```

**Step 4: 更新 config.example.yaml**

```yaml
# ... 现有配置 ...

long_short_ratio:
  periods:
    - "15m"
    - "1h"
  fetch_interval_minutes: 5

alerts:
  whale_flow:
    enabled: true
    threshold_usd: 10000000
  oi_change:
    enabled: true
    threshold_pct: 3
  liquidation:
    enabled: true
    threshold_usd: 20000000
  observe:
    enabled: true
    percentile_threshold: 90
  important:
    enabled: true
    percentile_threshold: 90
    min_dimensions: 3
```

**Step 5: 运行测试验证通过**

```bash
uv run pytest tests/test_config.py -v
```
Expected: PASS

**Step 6: 提交**

```bash
git add src/config.py tests/test_config.py config.example.yaml
git commit -m "feat: 更新配置结构，支持分级告警和多空比"
```

---

### Task 5.2: 集成到 main.py

**Files:**
- Modify: `src/main.py`
- Modify: `src/collector/indicator_fetcher.py`

**Step 1: 重写 indicator_fetcher.py 使用 BinanceClient**

`src/collector/indicator_fetcher.py`:
```python
"""指标采集器（使用自封装 BinanceClient）"""

from dataclasses import dataclass

from src.client.binance import BinanceClient


@dataclass
class Indicators:
    funding_rate: float
    long_short_ratio: float  # 保留兼容
    spot_price: float
    futures_price: float

    @property
    def spot_perp_spread(self) -> float:
        if self.spot_price == 0:
            return 0.0
        return (self.futures_price - self.spot_price) / self.spot_price * 100


@dataclass
class LongShortIndicators:
    global_ratio: float
    top_account_ratio: float
    top_position_ratio: float
    taker_ratio: float


class IndicatorFetcher:
    """指标采集器"""

    def __init__(self):
        self._client = BinanceClient()

    async def fetch_indicators(self, symbol: str) -> Indicators:
        """获取基础指标"""
        # 转换 symbol: BTC/USDT:USDT -> BTCUSDT
        ws_symbol = symbol.replace("/", "").replace(":USDT", "")

        async with self._client as client:
            funding = await client.get_funding_rate(ws_symbol)
            klines = await client.get_klines(ws_symbol, "1h", limit=1)
            global_ls = await client.get_global_long_short_ratio(ws_symbol, "1h")

        return Indicators(
            funding_rate=funding.funding_rate,
            long_short_ratio=global_ls.long_short_ratio,
            spot_price=klines[0].close if klines else 0,
            futures_price=klines[0].close if klines else 0,
        )

    async def fetch_long_short_indicators(self, symbol: str) -> LongShortIndicators:
        """获取 4 种多空比指标"""
        ws_symbol = symbol.replace("/", "").replace(":USDT", "")

        async with self._client as client:
            global_ls = await client.get_global_long_short_ratio(ws_symbol, "1h")
            top_account = await client.get_top_long_short_account_ratio(ws_symbol, "1h")
            top_position = await client.get_top_long_short_position_ratio(ws_symbol, "1h")
            taker = await client.get_taker_long_short_ratio(ws_symbol, "1h")

        return LongShortIndicators(
            global_ratio=global_ls.long_short_ratio,
            top_account_ratio=top_account.long_short_ratio,
            top_position_ratio=top_position.long_short_ratio,
            taker_ratio=taker.buy_sell_ratio,
        )

    async def fetch_open_interest(self, symbol: str) -> float:
        """获取持仓量"""
        ws_symbol = symbol.replace("/", "").replace(":USDT", "")

        async with self._client as client:
            oi = await client.get_open_interest(ws_symbol)

        return oi.open_interest
```

**Step 2: 更新 main.py 的告警检查逻辑**

在 `_check_insight_alerts` 方法中集成分级告警:
```python
async def _check_tiered_alerts(self, symbol: str) -> None:
    """检查分级告警"""
    from src.alert.trigger import check_tiered_alerts, AlertLevel
    from src.notifier.formatter import format_observe_alert, format_important_alert

    # 获取各维度百分位
    # ... 计算逻辑 ...

    percentiles = {
        "flow": flow_percentile,
        "oi_change": oi_percentile,
        "liquidation": liq_percentile,
        "funding_rate": funding_percentile,
        "global_ls": global_ls_percentile,
        "top_position_ls": top_position_percentile,
        "taker_ratio": taker_percentile,
    }

    alerts = check_tiered_alerts(
        percentiles,
        threshold=self.config.alerts.observe.percentile_threshold,
        min_dimensions=self.config.alerts.important.min_dimensions,
    )

    for alert in alerts:
        if alert.level == AlertLevel.OBSERVE and self.config.alerts.observe.enabled:
            # 发送观察提醒
            pass
        elif alert.level == AlertLevel.IMPORTANT and self.config.alerts.important.enabled:
            # 发送重要提醒
            pass
```

**Step 3: 运行完整测试**

```bash
uv run pytest tests/ -v
```
Expected: PASS

**Step 4: 运行格式化和类型检查**

```bash
uv run ruff check --fix . && uv run ruff format .
uv run mypy src/
```

**Step 5: 提交**

```bash
git add -A
git commit -m "feat: 集成 BinanceClient 和分级告警到主程序"
```

---

## Phase 6: 清理和最终验证

### Task 6.1: 清理无用代码

**Files:**
- 检查并删除所有 ccxt 相关 import
- 检查并删除所有 OKX 相关引用
- 更新 `src/aggregator/flow.py` 移除交易所区分逻辑

**Step 1: 搜索并清理 ccxt 引用**

```bash
rg "ccxt" src/
```

删除所有找到的 ccxt 相关代码。

**Step 2: 搜索并清理 OKX 引用**

```bash
rg -i "okx" src/
```

删除所有找到的 OKX 相关代码。

**Step 3: 更新 flow.py**

移除 `by_exchange` 字段或简化为只有 binance。

**Step 4: 运行测试**

```bash
uv run pytest tests/ -v
```

**Step 5: 提交**

```bash
git add -A
git commit -m "chore: 清理 ccxt 和 OKX 相关代码"
```

---

### Task 6.2: 最终验证

**Step 1: 运行所有测试**

```bash
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

**Step 2: 运行类型检查**

```bash
uv run mypy src/
```

**Step 3: 运行格式化检查**

```bash
uv run ruff check . && uv run ruff format --check .
```

**Step 4: 确认无错误后提交**

```bash
git add -A
git commit -m "test: 最终验证通过"
```

---

## 完成检查清单

- [ ] BinanceClient 封装完成，包含所有端点
- [ ] 4 种多空比数据采集正常
- [ ] long_short_snapshots 表创建并工作
- [ ] 分级告警（观察/重要）实现
- [ ] OKX 相关代码完全删除
- [ ] ccxt 依赖完全删除
- [ ] 所有测试通过
- [ ] mypy 类型检查通过
- [ ] ruff 格式检查通过

---

**设计版本**: v1.0
**创建时间**: 2026-02-01
