# BTC 市场洞察增强 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 增强 BTC 市场监控，添加大户vs散户分歧分析、主动买卖比、智能异动提醒，提供更全面的市场洞察。

**Architecture:** 在现有系统基础上增量升级。新增 3 个 Binance API 数据源，存入新表 `market_indicators`，新建 `insight` 模块计算分歧和生成总结，重写报告格式，添加异动检测触发器。

**Tech Stack:** Python 3.14, ccxt, aiosqlite, python-telegram-bot

---

## Task 1: 新增数据模型

**Files:**
- Modify: `src/storage/models.py`
- Test: `tests/storage/test_models.py`

**Step 1: 写失败测试**

```python
# tests/storage/test_models.py
def test_market_indicator_creation():
    from src.storage.models import MarketIndicator

    indicator = MarketIndicator(
        id=None,
        symbol="BTC/USDT:USDT",
        timestamp=1706600000000,
        top_account_ratio=1.5,
        top_position_ratio=1.6,
        global_account_ratio=0.9,
        taker_buy_sell_ratio=1.1,
    )
    assert indicator.symbol == "BTC/USDT:USDT"
    assert indicator.top_account_ratio == 1.5
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/storage/test_models.py::test_market_indicator_creation -v`
Expected: FAIL with "cannot import name 'MarketIndicator'"

**Step 3: 实现 MarketIndicator**

在 `src/storage/models.py` 末尾添加:

```python
@dataclass
class MarketIndicator:
    id: int | None
    symbol: str
    timestamp: int
    top_account_ratio: float      # 大户账户多空比
    top_position_ratio: float     # 大户持仓多空比
    global_account_ratio: float   # 散户账户多空比
    taker_buy_sell_ratio: float   # 主动买卖比
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/storage/test_models.py::test_market_indicator_creation -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/storage/models.py tests/storage/test_models.py
git commit -m "feat: 添加 MarketIndicator 数据模型"
```

---

## Task 2: 新增数据库表和 CRUD

**Files:**
- Modify: `src/storage/database.py`
- Test: `tests/storage/test_database.py`

**Step 1: 写失败测试**

在 `tests/storage/test_database.py` 末尾添加:

```python
async def test_insert_and_get_market_indicator(tmp_path):
    from src.storage.database import Database
    from src.storage.models import MarketIndicator

    db = Database(str(tmp_path / "test.db"))
    await db.init()

    indicator = MarketIndicator(
        id=None,
        symbol="BTC/USDT:USDT",
        timestamp=1706600000000,
        top_account_ratio=1.5,
        top_position_ratio=1.6,
        global_account_ratio=0.9,
        taker_buy_sell_ratio=1.1,
    )

    await db.insert_market_indicator(indicator)
    result = await db.get_latest_market_indicator("BTC/USDT:USDT")

    assert result is not None
    assert result.top_account_ratio == 1.5
    assert result.taker_buy_sell_ratio == 1.1

    await db.close()


async def test_get_market_indicator_history(tmp_path):
    from src.storage.database import Database
    from src.storage.models import MarketIndicator

    db = Database(str(tmp_path / "test.db"))
    await db.init()

    # 插入两条记录
    for i, ts in enumerate([1706600000000, 1706603600000]):
        indicator = MarketIndicator(
            id=None,
            symbol="BTC/USDT:USDT",
            timestamp=ts,
            top_account_ratio=1.5 + i * 0.1,
            top_position_ratio=1.6,
            global_account_ratio=0.9,
            taker_buy_sell_ratio=1.1,
        )
        await db.insert_market_indicator(indicator)

    history = await db.get_market_indicator_history("BTC/USDT:USDT", hours=2)
    assert len(history) == 2

    await db.close()
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/storage/test_database.py::test_insert_and_get_market_indicator -v`
Expected: FAIL with "has no attribute 'insert_market_indicator'"

**Step 3: 实现数据库方法**

在 `src/storage/database.py` 的 `_create_tables` 方法中添加表:

```python
CREATE TABLE IF NOT EXISTS market_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    top_account_ratio REAL NOT NULL,
    top_position_ratio REAL NOT NULL,
    global_account_ratio REAL NOT NULL,
    taker_buy_sell_ratio REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mi_symbol_time ON market_indicators(symbol, timestamp);
```

在 `Database` 类中添加方法:

```python
async def insert_market_indicator(self, mi: MarketIndicator) -> int:
    assert self.conn is not None
    cursor = await self.conn.execute(
        """INSERT INTO market_indicators
           (symbol, timestamp, top_account_ratio, top_position_ratio,
            global_account_ratio, taker_buy_sell_ratio)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            mi.symbol,
            mi.timestamp,
            mi.top_account_ratio,
            mi.top_position_ratio,
            mi.global_account_ratio,
            mi.taker_buy_sell_ratio,
        ),
    )
    await self.conn.commit()
    return cursor.lastrowid or 0

async def get_latest_market_indicator(self, symbol: str) -> MarketIndicator | None:
    assert self.conn is not None
    cursor = await self.conn.execute(
        """SELECT id, symbol, timestamp, top_account_ratio, top_position_ratio,
                  global_account_ratio, taker_buy_sell_ratio
           FROM market_indicators WHERE symbol = ?
           ORDER BY timestamp DESC LIMIT 1""",
        (symbol,),
    )
    row = await cursor.fetchone()
    return MarketIndicator(*row) if row else None

async def get_market_indicator_history(
    self, symbol: str, hours: int
) -> list[MarketIndicator]:
    assert self.conn is not None
    cutoff = int(time.time() * 1000) - hours * 3600 * 1000
    cursor = await self.conn.execute(
        """SELECT id, symbol, timestamp, top_account_ratio, top_position_ratio,
                  global_account_ratio, taker_buy_sell_ratio
           FROM market_indicators WHERE symbol = ? AND timestamp >= ?
           ORDER BY timestamp DESC""",
        (symbol, cutoff),
    )
    rows = await cursor.fetchall()
    return [MarketIndicator(*row) for row in rows]
```

记得在文件顶部导入:
```python
from .models import Liquidation, MarketIndicator, OISnapshot, PriceAlert, Trade
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/storage/test_database.py::test_insert_and_get_market_indicator tests/storage/test_database.py::test_get_market_indicator_history -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/storage/database.py tests/storage/test_database.py
git commit -m "feat: 添加 market_indicators 表和 CRUD 方法"
```

---

## Task 3: 新增 API 数据采集

**Files:**
- Modify: `src/collector/indicator_fetcher.py`
- Test: `tests/collector/test_indicator_fetcher.py`

**Step 1: 写失败测试**

在 `tests/collector/test_indicator_fetcher.py` 末尾添加:

```python
async def test_fetch_market_indicators():
    from unittest.mock import AsyncMock, MagicMock

    from src.collector.indicator_fetcher import IndicatorFetcher

    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    mock_exchange = MagicMock()

    # Mock 大户账户多空比
    mock_exchange.fetch_long_short_ratio_history = AsyncMock(
        return_value=[{"longShortRatio": 1.5, "timestamp": 1706600000000}]
    )

    # Mock 大户持仓多空比
    mock_exchange.fapiDataGetTopLongShortPositionRatio = AsyncMock(
        return_value=[{"longShortRatio": "1.6", "timestamp": "1706600000000"}]
    )

    # Mock 主动买卖比
    mock_exchange.fapiDataGetTakerlongshortRatio = AsyncMock(
        return_value=[{"buySellRatio": "1.1", "timestamp": "1706600000000"}]
    )

    fetcher.binance = mock_exchange

    result = await fetcher.fetch_market_indicators("BTC/USDT:USDT")

    assert result is not None
    assert result.top_account_ratio == 1.5
    assert result.top_position_ratio == 1.6
    assert result.taker_buy_sell_ratio == 1.1
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/collector/test_indicator_fetcher.py::test_fetch_market_indicators -v`
Expected: FAIL with "has no attribute 'fetch_market_indicators'"

**Step 3: 实现 fetch_market_indicators**

在 `src/collector/indicator_fetcher.py` 添加导入和方法:

```python
from src.storage.models import MarketIndicator, OISnapshot
```

在 `IndicatorFetcher` 类中添加:

```python
async def fetch_market_indicators(self, symbol: str) -> MarketIndicator | None:
    try:
        assert self.binance is not None

        raw_symbol = symbol.replace("/", "").replace(":USDT", "")

        # 大户账户多空比 (使用现有的 fetch_long_short_ratio_history)
        top_account_data = await self.binance.fetch_long_short_ratio_history(
            symbol, "5m", limit=1
        )
        top_account_ratio = float(top_account_data[-1]["longShortRatio"]) if top_account_data else 1.0

        # 大户持仓多空比
        top_position_data = await self.binance.fapiDataGetTopLongShortPositionRatio(
            {"symbol": raw_symbol, "period": "5m", "limit": 1}
        )
        top_position_ratio = float(top_position_data[0]["longShortRatio"]) if top_position_data else 1.0

        # 散户账户多空比 (全局账户)
        global_account_data = await self.binance.fapiDataGetGlobalLongShortAccountRatio(
            {"symbol": raw_symbol, "period": "5m", "limit": 1}
        )
        global_account_ratio = float(global_account_data[0]["longShortRatio"]) if global_account_data else 1.0

        # 主动买卖比
        taker_data = await self.binance.fapiDataGetTakerlongshortRatio(
            {"symbol": raw_symbol, "period": "5m", "limit": 1}
        )
        taker_ratio = float(taker_data[0]["buySellRatio"]) if taker_data else 1.0

        return MarketIndicator(
            id=None,
            symbol=symbol,
            timestamp=int(time.time() * 1000),
            top_account_ratio=top_account_ratio,
            top_position_ratio=top_position_ratio,
            global_account_ratio=global_account_ratio,
            taker_buy_sell_ratio=taker_ratio,
        )
    except Exception as e:
        logger.error(f"Failed to fetch market indicators for {symbol}: {e}")
        return None
```

在文件顶部添加 `import time`。

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/collector/test_indicator_fetcher.py::test_fetch_market_indicators -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/collector/indicator_fetcher.py tests/collector/test_indicator_fetcher.py
git commit -m "feat: 添加大户多空比、持仓比、主动买卖比 API 采集"
```

---

## Task 4: 新建 insight 计算模块

**Files:**
- Create: `src/aggregator/insight.py`
- Test: `tests/aggregator/test_insight.py`

**Step 1: 写失败测试**

创建 `tests/aggregator/test_insight.py`:

```python
# tests/aggregator/test_insight.py


def test_calculate_divergence_strong():
    from src.aggregator.insight import calculate_divergence

    result = calculate_divergence(
        top_ratio=1.8,
        global_ratio=0.8,
        history=[0.1, 0.2, 0.3, 0.4, 0.5],  # 历史分歧度
    )

    assert result["divergence"] == 1.0  # 1.8 - 0.8
    assert result["level"] == "strong"  # 1.0 远超历史


def test_calculate_divergence_none():
    from src.aggregator.insight import calculate_divergence

    result = calculate_divergence(
        top_ratio=1.0,
        global_ratio=1.0,
        history=[0.1, 0.2, 0.3, 0.4, 0.5],
    )

    assert result["divergence"] == 0.0
    assert result["level"] == "none"


def test_calculate_change():
    from src.aggregator.insight import calculate_change

    result = calculate_change(current=1.5, previous=1.2)

    assert result["diff"] == 0.3
    assert result["direction"] == "↑"


def test_generate_summary():
    from src.aggregator.insight import generate_summary

    data = {
        "top_ratio_change": 0.1,       # 大户加多
        "divergence": 0.5,
        "divergence_level": "strong",  # 显著分歧
        "flow_1h": 5_000_000,          # 资金流入
        "liq_long_ratio": 0.3,         # 空头承压
    }

    summary = generate_summary(data)

    assert "大户加多" in summary
    assert "分歧" in summary
    assert "资金流入" in summary
    assert "空头承压" in summary
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/aggregator/test_insight.py -v`
Expected: FAIL with "No module named 'src.aggregator.insight'"

**Step 3: 实现 insight 模块**

创建 `src/aggregator/insight.py`:

```python
# src/aggregator/insight.py
from src.aggregator.percentile import calculate_percentile


def calculate_divergence(
    top_ratio: float,
    global_ratio: float,
    history: list[float],
    mild_pct: float = 75,
    strong_pct: float = 90,
) -> dict:
    """
    计算大户与散户的分歧程度

    Args:
        top_ratio: 大户持仓多空比
        global_ratio: 散户账户多空比
        history: 历史分歧度列表
        mild_pct: 轻度分歧百分位阈值
        strong_pct: 显著分歧百分位阈值

    Returns:
        divergence: 分歧度 (正=大户更看多, 负=大户更看空)
        percentile: 当前分歧在历史中的百分位
        level: 分歧级别 (none/mild/strong)
    """
    divergence = top_ratio - global_ratio
    percentile = calculate_percentile(abs(divergence), history)

    if percentile < mild_pct:
        level = "none"
    elif percentile < strong_pct:
        level = "mild"
    else:
        level = "strong"

    return {
        "divergence": divergence,
        "percentile": percentile,
        "level": level,
    }


def calculate_change(current: float, previous: float) -> dict:
    """计算指标变化"""
    diff = current - previous
    if diff > 0.001:
        direction = "↑"
    elif diff < -0.001:
        direction = "↓"
    else:
        direction = "→"

    return {"diff": round(diff, 4), "direction": direction}


def generate_summary(data: dict) -> str:
    """
    生成一句话市场总结（规则版）

    预留接口供未来 AI 替换
    """
    parts = []

    # 大户动向
    top_change = data.get("top_ratio_change", 0)
    if top_change > 0.05:
        parts.append("大户加多")
    elif top_change < -0.05:
        parts.append("大户减多")

    # 分歧情况
    div_level = data.get("divergence_level", "none")
    div = data.get("divergence", 0)
    if div_level == "strong":
        if div > 0:
            parts.append("与散户分歧（大户更看多）")
        else:
            parts.append("与散户分歧（大户更看空）")
    elif div_level == "mild":
        parts.append("大户散户轻度分歧")

    # 资金流向
    flow = data.get("flow_1h", 0)
    if flow > 1_000_000:
        parts.append("资金流入")
    elif flow < -1_000_000:
        parts.append("资金流出")

    # 爆仓压力
    liq_long_ratio = data.get("liq_long_ratio", 0.5)
    if liq_long_ratio > 0.65:
        parts.append("多头承压")
    elif liq_long_ratio < 0.35:
        parts.append("空头承压")

    return "，".join(parts) if parts else "市场平稳"
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/aggregator/test_insight.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/aggregator/insight.py tests/aggregator/test_insight.py
git commit -m "feat: 添加 insight 模块 - 分歧计算和总结生成"
```

---

## Task 5: 新建异动检测模块

**Files:**
- Create: `src/alert/insight_trigger.py`
- Test: `tests/alert/test_insight_trigger.py`

**Step 1: 写失败测试**

创建 `tests/alert/test_insight_trigger.py`:

```python
# tests/alert/test_insight_trigger.py
from dataclasses import dataclass


def test_detect_divergence_spike():
    from src.alert.insight_trigger import check_insight_alerts

    current = {"divergence_level": "strong", "top_ratio": 1.5, "flow_1h": 100, "taker_ratio_pct": 50}
    previous = {"divergence_level": "none", "top_ratio": 1.4, "flow_1h": 50, "taker_ratio_pct": 50}

    alerts = check_insight_alerts(current, previous)

    assert len(alerts) == 1
    assert alerts[0].type == "divergence_spike"


def test_detect_whale_flip():
    from src.alert.insight_trigger import check_insight_alerts

    current = {"divergence_level": "none", "top_ratio": 1.1, "flow_1h": 100, "taker_ratio_pct": 50}
    previous = {"divergence_level": "none", "top_ratio": 0.9, "flow_1h": 50, "taker_ratio_pct": 50}

    alerts = check_insight_alerts(current, previous)

    assert len(alerts) == 1
    assert alerts[0].type == "whale_flip"


def test_detect_flow_reversal():
    from src.alert.insight_trigger import check_insight_alerts

    current = {"divergence_level": "none", "top_ratio": 1.0, "flow_1h": 6_000_000, "taker_ratio_pct": 50}
    previous = {"divergence_level": "none", "top_ratio": 1.0, "flow_1h": -1_000_000, "taker_ratio_pct": 50}

    alerts = check_insight_alerts(current, previous, flow_threshold=5_000_000)

    assert len(alerts) == 1
    assert alerts[0].type == "flow_reversal"


def test_no_alerts_when_stable():
    from src.alert.insight_trigger import check_insight_alerts

    current = {"divergence_level": "none", "top_ratio": 1.0, "flow_1h": 100, "taker_ratio_pct": 50}
    previous = {"divergence_level": "none", "top_ratio": 1.0, "flow_1h": 50, "taker_ratio_pct": 50}

    alerts = check_insight_alerts(current, previous)

    assert len(alerts) == 0
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/alert/test_insight_trigger.py -v`
Expected: FAIL with "No module named 'src.alert.insight_trigger'"

**Step 3: 实现异动检测**

创建 `src/alert/insight_trigger.py`:

```python
# src/alert/insight_trigger.py
from dataclasses import dataclass


@dataclass
class InsightAlert:
    type: str       # divergence_spike, whale_flip, flow_reversal, taker_extreme
    message: str


def check_insight_alerts(
    current: dict,
    previous: dict,
    flow_threshold: float = 5_000_000,
) -> list[InsightAlert]:
    """
    检测市场异动

    Args:
        current: 当前市场指标
        previous: 上一周期市场指标
        flow_threshold: 资金反转阈值

    Returns:
        触发的异动提醒列表
    """
    alerts = []

    # 1. 大户散户分歧突变
    if (current["divergence_level"] == "strong" and
        previous["divergence_level"] != "strong"):
        alerts.append(InsightAlert(
            type="divergence_spike",
            message="大户散户分歧加剧"
        ))

    # 2. 大户方向反转 (多空比跨越 1.0)
    curr_top = current["top_ratio"]
    prev_top = previous["top_ratio"]
    if (curr_top > 1 and prev_top < 1) or (curr_top < 1 and prev_top > 1):
        direction = "转多" if curr_top > 1 else "转空"
        alerts.append(InsightAlert(
            type="whale_flip",
            message=f"大户方向反转：{direction}"
        ))

    # 3. 资金流向反转
    curr_flow = current["flow_1h"]
    prev_flow = previous["flow_1h"]
    if ((curr_flow > 0 and prev_flow < 0) or (curr_flow < 0 and prev_flow > 0)):
        if abs(curr_flow) > flow_threshold:
            direction = "转为流入" if curr_flow > 0 else "转为流出"
            alerts.append(InsightAlert(
                type="flow_reversal",
                message=f"资金流向反转：{direction}"
            ))

    # 4. 主动买卖比极端值
    if current["taker_ratio_pct"] > 90:
        direction = "主动买入极端" if current.get("taker_ratio", 1) > 1 else "主动卖出极端"
        alerts.append(InsightAlert(
            type="taker_extreme",
            message=direction
        ))

    return alerts
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/alert/test_insight_trigger.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/alert/insight_trigger.py tests/alert/test_insight_trigger.py
git commit -m "feat: 添加异动检测模块"
```

---

## Task 6: 重写报告格式

**Files:**
- Modify: `src/notifier/formatter.py`
- Test: `tests/notifier/test_formatter.py`

**Step 1: 写失败测试**

在 `tests/notifier/test_formatter.py` 末尾添加:

```python
def test_format_insight_report():
    from src.notifier.formatter import format_insight_report

    data = {
        "symbol": "BTC",
        "price": 83200,
        "price_change_1h": 1.2,
        "summary": "大户加多，与散户分歧，资金流入",
        # 大户 vs 散户
        "top_position_ratio": 1.52,
        "top_position_change": 0.12,
        "top_position_pct": 65,
        "global_account_ratio": 0.88,
        "global_account_change": -0.08,
        "global_account_pct": 58,
        "divergence": 0.64,
        "divergence_pct": 92,
        "divergence_level": "strong",
        # 资金动向
        "taker_ratio": 1.15,
        "taker_ratio_change": 0.05,
        "taker_ratio_pct": 62,
        "flow_1h": 5_200_000,
        "flow_1h_pct": 58,
        "flow_binance": 3_800_000,
        "flow_okx": 1_400_000,
        # 持仓 & 爆仓
        "oi_value": 18_200_000_000,
        "oi_change_1h": 1.2,
        "oi_change_1h_pct": 55,
        "liq_1h_total": 7_400_000,
        "liq_long_ratio": 0.32,
        # 情绪指标
        "funding_rate": 0.012,
        "funding_rate_pct": 48,
        "spot_perp_spread": 0.05,
        "spot_perp_spread_pct": 44,
    }

    result = format_insight_report(data)

    assert "BTC 市场洞察" in result
    assert "大户加多" in result
    assert "大户 vs 散户" in result
    assert "1.52" in result
    assert "资金动向" in result
    assert "空头承压" in result
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/notifier/test_formatter.py::test_format_insight_report -v`
Expected: FAIL with "cannot import name 'format_insight_report'"

**Step 3: 实现新报告格式**

在 `src/notifier/formatter.py` 末尾添加:

```python
def format_insight_report(data: dict[str, Any]) -> str:
    """生成市场洞察报告"""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # 大户 vs 散户
    top_dir = "↑" if data["top_position_change"] > 0 else "↓"
    global_dir = "↑" if data["global_account_change"] > 0 else "↓"

    # 分歧描述
    if data["divergence_level"] == "strong":
        div_desc = "大户更看多" if data["divergence"] > 0 else "大户更看空"
        div_line = f"  ⚠️ 分歧度: {data['divergence']:.2f} 🔴 P{int(data['divergence_pct'])} ({div_desc})"
    elif data["divergence_level"] == "mild":
        div_desc = "大户偏多" if data["divergence"] > 0 else "大户偏空"
        div_line = f"  分歧度: {data['divergence']:.2f} 🟡 P{int(data['divergence_pct'])} ({div_desc})"
    else:
        div_line = f"  分歧度: {data['divergence']:.2f} 🟢 P{int(data['divergence_pct'])} (一致)"

    # 主动买卖
    taker_dir = "↑" if data["taker_ratio_change"] > 0 else "↓"

    # 资金流向
    flow_1h = _format_usd_signed(data["flow_1h"])
    flow_binance = _format_usd_signed(data["flow_binance"])
    flow_okx = _format_usd_signed(data["flow_okx"])
    consistency = "✓一致" if (data["flow_binance"] >= 0) == (data["flow_okx"] >= 0) else "⚠️分歧"

    # 爆仓压力
    liq_long_pct = int(data["liq_long_ratio"] * 100)
    liq_short_pct = 100 - liq_long_pct
    if data["liq_long_ratio"] > 0.65:
        liq_pressure = "← 多头承压"
    elif data["liq_long_ratio"] < 0.35:
        liq_pressure = "← 空头承压"
    else:
        liq_pressure = ""

    return f"""📊 {data["symbol"]} 市场洞察
⏰ {now}

🎯 {data["summary"]}

━━━━━━━━━━━━━━━━━━━━
💵 价格: ${data["price"]:,.0f} ({data["price_change_1h"]:+.1f}% 1h)

━━━━━━━━━━━━━━━━━━━━
🐋 大户 vs 散户
  大户持仓比: {data["top_position_ratio"]:.2f} ({top_dir}{abs(data["top_position_change"]):.2f} vs 1h) {_level(data["top_position_pct"])}
  散户账户比: {data["global_account_ratio"]:.2f} ({global_dir}{abs(data["global_account_change"]):.2f} vs 1h) {_level(data["global_account_pct"])}
{div_line}

━━━━━━━━━━━━━━━━━━━━
💰 资金动向
  主动买卖比: {data["taker_ratio"]:.2f} ({taker_dir}{abs(data["taker_ratio_change"]):.2f} vs 1h) {_level(data["taker_ratio_pct"])}
  大单净流向: {flow_1h} {_level(data["flow_1h_pct"])}
    Binance: {flow_binance} | OKX: {flow_okx} {consistency}

━━━━━━━━━━━━━━━━━━━━
📈 持仓 & 爆仓
  OI: {_format_usd(data["oi_value"])} ({data["oi_change_1h"]:+.1f}% vs 1h) {_level(data["oi_change_1h_pct"])}
  爆仓 1h: {_format_usd(data["liq_1h_total"])} (多{liq_long_pct}% / 空{liq_short_pct}%) {liq_pressure}

━━━━━━━━━━━━━━━━━━━━
📊 情绪指标
  资金费率: {data["funding_rate"]:+.3f}% {_level(data["funding_rate_pct"])}
  合约溢价: {data["spot_perp_spread"]:+.2f}% {_level(data["spot_perp_spread_pct"])}"""
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/notifier/test_formatter.py::test_format_insight_report -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/notifier/formatter.py tests/notifier/test_formatter.py
git commit -m "feat: 添加市场洞察报告格式"
```

---

## Task 7: 更新配置文件

**Files:**
- Modify: `config.yaml`
- Modify: `src/config.py`
- Test: `tests/test_config.py`

**Step 1: 写失败测试**

在 `tests/test_config.py` 中添加:

```python
def test_load_insight_config(tmp_path):
    from src.config import load_config

    config_content = """
exchanges:
  binance:
    enabled: true
  okx:
    enabled: true

symbols:
  - BTC/USDT:USDT

thresholds:
  default_usd: 100000
  percentile: 95
  update_interval_hours: 1

intervals:
  oi_fetch_minutes: 5
  indicator_fetch_minutes: 5
  report_hours: 8
  cleanup_hours: 24

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

telegram:
  bot_token: "test"
  chat_id: "123"

database:
  path: "data/test.db"
  retention_days: 7

price_alerts:
  cooldown_minutes: 60

percentile:
  window_days: 7
  update_interval_minutes: 60

percentile_levels:
  normal_below: 75
  warning_below: 90

insight:
  enabled: true
  divergence:
    mild_percentile: 75
    strong_percentile: 90
  alerts:
    divergence_spike: true
    whale_flip: true
    flow_reversal: true
    flow_threshold_usd: 5000000
    cooldown_minutes: 30
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(config_file)

    assert config.insight.enabled is True
    assert config.insight.divergence.mild_percentile == 75
    assert config.insight.alerts.flow_threshold_usd == 5000000
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/test_config.py::test_load_insight_config -v`
Expected: FAIL with "has no attribute 'insight'"

**Step 3: 更新配置模型**

在 `src/config.py` 添加新的配置类:

```python
@dataclass
class DivergenceConfig:
    mild_percentile: int = 75
    strong_percentile: int = 90


@dataclass
class InsightAlertsConfig:
    divergence_spike: bool = True
    whale_flip: bool = True
    flow_reversal: bool = True
    flow_threshold_usd: int = 5_000_000
    cooldown_minutes: int = 30


@dataclass
class InsightConfig:
    enabled: bool = True
    divergence: DivergenceConfig = field(default_factory=DivergenceConfig)
    alerts: InsightAlertsConfig = field(default_factory=InsightAlertsConfig)
```

在 `Config` 类中添加:

```python
@dataclass
class Config:
    exchanges: ExchangesConfig
    symbols: list[str]
    thresholds: ThresholdsConfig
    intervals: IntervalsConfig
    alerts: AlertsConfig
    telegram: TelegramConfig
    database: DatabaseConfig
    price_alerts: PriceAlertsConfig
    percentile: PercentileConfig
    percentile_levels: PercentileLevelsConfig
    insight: InsightConfig = field(default_factory=InsightConfig)  # 新增
```

更新 `load_config` 函数中的解析逻辑:

```python
def load_config(path: Path) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)

    # ... 现有代码 ...

    insight_data = data.get("insight", {})
    insight = InsightConfig(
        enabled=insight_data.get("enabled", True),
        divergence=DivergenceConfig(
            mild_percentile=insight_data.get("divergence", {}).get("mild_percentile", 75),
            strong_percentile=insight_data.get("divergence", {}).get("strong_percentile", 90),
        ),
        alerts=InsightAlertsConfig(
            divergence_spike=insight_data.get("alerts", {}).get("divergence_spike", True),
            whale_flip=insight_data.get("alerts", {}).get("whale_flip", True),
            flow_reversal=insight_data.get("alerts", {}).get("flow_reversal", True),
            flow_threshold_usd=insight_data.get("alerts", {}).get("flow_threshold_usd", 5_000_000),
            cooldown_minutes=insight_data.get("alerts", {}).get("cooldown_minutes", 30),
        ),
    )

    return Config(
        # ... 现有字段 ...
        insight=insight,
    )
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 5: 更新 config.yaml**

在 `config.yaml` 末尾添加:

```yaml
# 市场洞察配置
insight:
  enabled: true

  # 分歧判断
  divergence:
    mild_percentile: 75     # P75 以上算轻度分歧
    strong_percentile: 90   # P90 以上算显著分歧

  # 异动提醒
  alerts:
    divergence_spike: true   # 分歧突变
    whale_flip: true         # 大户反转
    flow_reversal: true      # 资金反转
    flow_threshold_usd: 5000000  # 资金反转阈值
    cooldown_minutes: 30     # 同类型提醒冷却
```

**Step 6: 提交**

```bash
git add src/config.py tests/test_config.py config.yaml
git commit -m "feat: 添加 insight 配置项"
```

---

## Task 8: 集成到主程序

**Files:**
- Modify: `src/main.py`

**Step 1: 添加 market indicators 采集**

在 `CryptoMonitor` 类的 `_fetch_indicators` 方法中添加:

```python
async def _fetch_indicators(self) -> None:
    interval = self.config.intervals.oi_fetch_minutes * 60
    while self.running:
        try:
            # 现有 OI 采集
            oi_snapshots = await self.indicator_fetcher.fetch_all_oi()
            for oi in oi_snapshots:
                await self.db.insert_oi_snapshot(oi)

            # 新增：市场指标采集
            if self.config.insight.enabled:
                for symbol in self.config.symbols:
                    mi = await self.indicator_fetcher.fetch_market_indicators(symbol)
                    if mi:
                        await self.db.insert_market_indicator(mi)

        except Exception as e:
            logger.error(f"Failed to fetch indicators: {e}")
        await asyncio.sleep(interval)
```

**Step 2: 更新报告生成**

创建新方法 `_generate_insight_report`:

```python
async def _generate_insight_report(self, symbol: str) -> str:
    from src.aggregator.insight import calculate_change, calculate_divergence, generate_summary
    from src.notifier.formatter import format_insight_report

    # 获取当前和历史市场指标
    current_mi = await self.db.get_latest_market_indicator(symbol)
    history_mi = await self.db.get_market_indicator_history(symbol, hours=24)

    if not current_mi:
        return await self._generate_report(symbol)  # 回退到旧报告

    # 获取 1h 前的指标用于计算变化
    mi_1h_ago = None
    one_hour_ago = int(time.time() * 1000) - 3600 * 1000
    for mi in history_mi:
        if mi.timestamp <= one_hour_ago:
            mi_1h_ago = mi
            break

    if not mi_1h_ago:
        mi_1h_ago = current_mi  # 数据不足时用当前值

    # 计算分歧历史
    divergence_history = [
        abs(mi.top_position_ratio - mi.global_account_ratio)
        for mi in history_mi
    ]

    divergence_result = calculate_divergence(
        current_mi.top_position_ratio,
        current_mi.global_account_ratio,
        divergence_history,
        self.config.insight.divergence.mild_percentile,
        self.config.insight.divergence.strong_percentile,
    )

    # 获取其他数据
    trades_1h = await self.db.get_trades(symbol, hours=1)
    flow_1h = calculate_flow(trades_1h)

    liqs_1h = await self.db.get_liquidations(symbol, hours=1)
    liq_stats = calculate_liquidations(liqs_1h)
    liq_long_ratio = liq_stats.long / liq_stats.total if liq_stats.total > 0 else 0.5

    current_oi = await self.db.get_latest_oi(symbol)
    past_oi_1h = await self.db.get_oi_at(symbol, hours_ago=1)
    oi_change_1h = calculate_oi_change(current_oi, past_oi_1h)

    indicators = await self.indicator_fetcher.fetch_indicators(symbol)

    # 计算变化
    top_change = calculate_change(current_mi.top_position_ratio, mi_1h_ago.top_position_ratio)
    global_change = calculate_change(current_mi.global_account_ratio, mi_1h_ago.global_account_ratio)
    taker_change = calculate_change(current_mi.taker_buy_sell_ratio, mi_1h_ago.taker_buy_sell_ratio)

    # 生成总结
    summary_data = {
        "top_ratio_change": top_change["diff"],
        "divergence": divergence_result["divergence"],
        "divergence_level": divergence_result["level"],
        "flow_1h": flow_1h.net,
        "liq_long_ratio": liq_long_ratio,
    }
    summary = generate_summary(summary_data)

    # 组装报告数据
    data = {
        "symbol": symbol.split("/")[0],
        "price": indicators.futures_price if indicators else 0,
        "price_change_1h": 0,  # 需要从历史价格计算
        "summary": summary,
        # 大户 vs 散户
        "top_position_ratio": current_mi.top_position_ratio,
        "top_position_change": top_change["diff"],
        "top_position_pct": 50,  # 需要计算百分位
        "global_account_ratio": current_mi.global_account_ratio,
        "global_account_change": global_change["diff"],
        "global_account_pct": 50,
        "divergence": divergence_result["divergence"],
        "divergence_pct": divergence_result["percentile"],
        "divergence_level": divergence_result["level"],
        # 资金动向
        "taker_ratio": current_mi.taker_buy_sell_ratio,
        "taker_ratio_change": taker_change["diff"],
        "taker_ratio_pct": 50,
        "flow_1h": flow_1h.net,
        "flow_1h_pct": 50,
        "flow_binance": flow_1h.by_exchange.get("binance", 0),
        "flow_okx": flow_1h.by_exchange.get("okx", 0),
        # 持仓 & 爆仓
        "oi_value": current_oi.open_interest_usd if current_oi else 0,
        "oi_change_1h": oi_change_1h,
        "oi_change_1h_pct": 50,
        "liq_1h_total": liq_stats.total,
        "liq_long_ratio": liq_long_ratio,
        # 情绪指标
        "funding_rate": indicators.funding_rate if indicators else 0,
        "funding_rate_pct": 50,
        "spot_perp_spread": indicators.spot_perp_spread if indicators else 0,
        "spot_perp_spread_pct": 50,
    }

    return format_insight_report(data)
```

**Step 3: 更新定时报告调用**

```python
async def _scheduled_report(self) -> None:
    interval = self.config.intervals.report_hours * 3600
    while self.running:
        await asyncio.sleep(interval)
        for symbol in self.config.symbols:
            try:
                if self.config.insight.enabled:
                    report = await self._generate_insight_report(symbol)
                else:
                    report = await self._generate_report(symbol)
                await self.notifier.send_message(report)
            except Exception as e:
                logger.error(f"Failed to send report for {symbol}: {e}")
```

**Step 4: 添加异动检测**

新增方法并集成到主循环:

```python
async def _check_insight_alerts(self) -> None:
    """检测市场异动"""
    from src.alert.insight_trigger import check_insight_alerts

    if not self.config.insight.enabled:
        return

    # 存储上一次的状态
    previous_states: dict[str, dict] = {}

    while self.running:
        await asyncio.sleep(60)  # 每分钟检查

        for symbol in self.config.symbols:
            try:
                current_mi = await self.db.get_latest_market_indicator(symbol)
                if not current_mi:
                    continue

                trades_1h = await self.db.get_trades(symbol, hours=1)
                flow = calculate_flow(trades_1h)

                # 计算分歧
                history_mi = await self.db.get_market_indicator_history(symbol, hours=24)
                divergence_history = [
                    abs(mi.top_position_ratio - mi.global_account_ratio)
                    for mi in history_mi
                ]
                divergence_result = calculate_divergence(
                    current_mi.top_position_ratio,
                    current_mi.global_account_ratio,
                    divergence_history,
                )

                current_state = {
                    "divergence_level": divergence_result["level"],
                    "top_ratio": current_mi.top_position_ratio,
                    "flow_1h": flow.net,
                    "taker_ratio": current_mi.taker_buy_sell_ratio,
                    "taker_ratio_pct": 50,  # 需要计算
                }

                if symbol in previous_states:
                    alerts = check_insight_alerts(
                        current_state,
                        previous_states[symbol],
                        self.config.insight.alerts.flow_threshold_usd,
                    )

                    for alert in alerts:
                        # 发送异动提醒
                        msg = f"⚡ {symbol.split('/')[0]} 市场异动\n\n{alert.message}"
                        await self.notifier.send_message(msg)

                previous_states[symbol] = current_state

            except Exception as e:
                logger.error(f"Failed to check insight alerts for {symbol}: {e}")
```

在 `run` 方法中添加任务:

```python
tasks = [
    asyncio.create_task(self._scheduled_report()),
    asyncio.create_task(self._fetch_indicators()),
    asyncio.create_task(self._check_alerts()),
    asyncio.create_task(self._check_insight_alerts()),  # 新增
]
```

**Step 5: 提交**

```bash
git add src/main.py
git commit -m "feat: 集成市场洞察功能到主程序"
```

---

## Task 9: 运行全部测试

**Step 1: 运行全部测试**

Run: `uv run pytest tests/ -v`
Expected: 所有测试 PASS

**Step 2: 运行格式检查**

Run: `uv run ruff check --fix . && uv run ruff format .`
Expected: 无错误

**Step 3: 运行类型检查**

Run: `uv run mypy src/`
Expected: 无错误（或只有已知忽略项）

**Step 4: 提交**

```bash
git add .
git commit -m "chore: 格式化和类型检查修复"
```

---

## Task 10: 集成测试

**Step 1: 启动系统测试**

Run: `uv run python -m src.main`

验证:
1. 日志显示 market indicators 采集成功
2. Telegram 发送 `/report BTC` 返回新格式报告
3. 无错误日志

**Step 2: 最终提交**

```bash
git add .
git commit -m "feat: BTC 市场洞察增强功能完成"
```

---

## 总结

| Task | 内容 | 估计复杂度 |
|------|------|-----------|
| 1 | 数据模型 | 低 |
| 2 | 数据库 CRUD | 低 |
| 3 | API 采集 | 中 |
| 4 | insight 计算 | 中 |
| 5 | 异动检测 | 中 |
| 6 | 报告格式 | 中 |
| 7 | 配置文件 | 低 |
| 8 | 主程序集成 | 高 |
| 9 | 测试验证 | 低 |
| 10 | 集成测试 | 低 |
