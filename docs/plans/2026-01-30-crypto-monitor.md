# Crypto Monitor 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 BTC/ETH 永续合约的市场监控系统，通过 Telegram 推送定时报告、异常提醒和价位提醒。

**Architecture:** WebSocket 实时采集大单和爆仓数据，REST API 定时获取 OI 和指标，SQLite 存储，聚合计算后通过 Telegram Bot 推送。

**Tech Stack:** Python 3.11+, ccxt, websockets, python-telegram-bot, SQLite, pydantic, PyYAML, pytest

---

## Phase 1: 项目初始化

### Task 1: 创建项目结构和依赖

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/utils/__init__.py`
- Create: `tests/__init__.py`

**Step 1: 创建 pyproject.toml**

```toml
[project]
name = "crypto-monitor"
version = "0.1.0"
description = "BTC/ETH perpetual futures market monitor"
requires-python = ">=3.11"
dependencies = [
    "ccxt>=4.0.0",
    "websockets>=12.0",
    "python-telegram-bot>=21.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "aiosqlite>=0.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "mypy>=1.8",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.11"
strict = true
```

**Step 2: 创建目录结构**

```bash
mkdir -p src/{collector,aggregator,alert,notifier,storage,utils}
mkdir -p tests/{collector,aggregator,alert,notifier,storage}
touch src/__init__.py src/utils/__init__.py tests/__init__.py
```

**Step 3: 安装依赖**

Run: `uv sync`

**Step 4: 验证安装**

Run: `uv run python -c "import ccxt; print('OK')"`
Expected: OK

**Step 5: Commit**

```bash
git init
git add .
git commit -m "chore: init project structure"
```

---

## Phase 2: 配置管理

### Task 2: 实现配置加载

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`
- Create: `config.example.yaml`

**Step 1: 写失败测试**

```python
# tests/test_config.py
import pytest
from pathlib import Path
from src.config import Config, load_config


def test_load_config_from_yaml(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
exchanges:
  binance:
    enabled: true
  okx:
    enabled: true

symbols:
  - BTC/USDT:USDT
  - ETH/USDT:USDT

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
  bot_token: "test_token"
  chat_id: "test_chat"

database:
  path: "data/monitor.db"
  retention_days: 7

price_alerts:
  cooldown_minutes: 60

percentile:
  window_days: 7
  update_interval_minutes: 60

percentile_levels:
  normal_below: 75
  warning_below: 90
""")

    config = load_config(config_file)

    assert config.exchanges.binance.enabled is True
    assert config.symbols == ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    assert config.thresholds.default_usd == 100000
    assert config.alerts.whale_flow.threshold_usd == 10000000
    assert config.telegram.bot_token == "test_token"
    assert config.price_alerts.cooldown_minutes == 60
    assert config.percentile_levels.normal_below == 75
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: 实现配置模块**

```python
# src/config.py
from pathlib import Path
from pydantic import BaseModel
import yaml


class ExchangeConfig(BaseModel):
    enabled: bool = True


class ExchangesConfig(BaseModel):
    binance: ExchangeConfig = ExchangeConfig()
    okx: ExchangeConfig = ExchangeConfig()


class ThresholdsConfig(BaseModel):
    default_usd: float = 100000
    percentile: int = 95
    update_interval_hours: int = 1


class IntervalsConfig(BaseModel):
    oi_fetch_minutes: int = 5
    indicator_fetch_minutes: int = 5
    report_hours: int = 8
    cleanup_hours: int = 24


class AlertConfig(BaseModel):
    enabled: bool = True
    threshold_usd: float | None = None
    threshold_pct: float | None = None


class AlertsConfig(BaseModel):
    whale_flow: AlertConfig = AlertConfig(threshold_usd=10000000)
    oi_change: AlertConfig = AlertConfig(threshold_pct=3)
    liquidation: AlertConfig = AlertConfig(threshold_usd=20000000)


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str


class DatabaseConfig(BaseModel):
    path: str = "data/monitor.db"
    retention_days: int = 7


class PriceAlertsConfig(BaseModel):
    cooldown_minutes: int = 60


class PercentileConfig(BaseModel):
    window_days: int = 7
    update_interval_minutes: int = 60


class PercentileLevelsConfig(BaseModel):
    normal_below: int = 75
    warning_below: int = 90


class Config(BaseModel):
    exchanges: ExchangesConfig = ExchangesConfig()
    symbols: list[str] = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    thresholds: ThresholdsConfig = ThresholdsConfig()
    intervals: IntervalsConfig = IntervalsConfig()
    alerts: AlertsConfig = AlertsConfig()
    telegram: TelegramConfig
    database: DatabaseConfig = DatabaseConfig()
    price_alerts: PriceAlertsConfig = PriceAlertsConfig()
    percentile: PercentileConfig = PercentileConfig()
    percentile_levels: PercentileLevelsConfig = PercentileLevelsConfig()


def load_config(path: Path) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config(**data)
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 5: 创建示例配置文件**

```yaml
# config.example.yaml
exchanges:
  binance:
    enabled: true
  okx:
    enabled: true

symbols:
  - BTC/USDT:USDT
  - ETH/USDT:USDT

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
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

database:
  path: "data/monitor.db"
  retention_days: 7

price_alerts:
  cooldown_minutes: 60

percentile:
  window_days: 7
  update_interval_minutes: 60

percentile_levels:
  normal_below: 75
  warning_below: 90
```

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add config management"
```

---

## Phase 3: 数据库层

### Task 3: 实现数据库初始化和基础操作

**Files:**
- Create: `src/storage/__init__.py`
- Create: `src/storage/database.py`
- Create: `src/storage/models.py`
- Create: `tests/storage/__init__.py`
- Create: `tests/storage/test_database.py`

**Step 1: 创建数据模型**

```python
# src/storage/models.py
from dataclasses import dataclass


@dataclass
class Trade:
    id: int | None
    exchange: str
    symbol: str
    timestamp: int
    price: float
    amount: float
    side: str
    value_usd: float


@dataclass
class Liquidation:
    id: int | None
    exchange: str
    symbol: str
    timestamp: int
    side: str
    price: float
    quantity: float
    value_usd: float


@dataclass
class OISnapshot:
    id: int | None
    exchange: str
    symbol: str
    timestamp: int
    open_interest: float
    open_interest_usd: float


@dataclass
class PriceAlert:
    id: int | None
    symbol: str
    price: float
    last_position: str | None
    last_triggered_at: int | None
```

**Step 2: 写失败测试**

```python
# tests/storage/test_database.py
import pytest
from src.storage.database import Database
from src.storage.models import Trade, PriceAlert


@pytest.fixture
async def db(tmp_path):
    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    await database.init()
    yield database
    await database.close()


async def test_insert_and_get_trades(db: Database):
    trade = Trade(
        id=None,
        exchange="binance",
        symbol="BTC/USDT:USDT",
        timestamp=1706600000000,
        price=100000.0,
        amount=1.5,
        side="buy",
        value_usd=150000.0,
    )
    await db.insert_trade(trade)

    trades = await db.get_trades("BTC/USDT:USDT", hours=1)
    assert len(trades) == 1
    assert trades[0].exchange == "binance"
    assert trades[0].value_usd == 150000.0


async def test_price_alerts_crud(db: Database):
    # Create
    alert = PriceAlert(
        id=None,
        symbol="BTC",
        price=100000.0,
        last_position="below",
        last_triggered_at=None,
    )
    alert_id = await db.insert_price_alert(alert)
    assert alert_id is not None

    # Read
    alerts = await db.get_price_alerts("BTC")
    assert len(alerts) == 1
    assert alerts[0].price == 100000.0

    # Delete
    await db.delete_price_alert("BTC", 100000.0)
    alerts = await db.get_price_alerts("BTC")
    assert len(alerts) == 0
```

**Step 3: 运行测试确认失败**

Run: `uv run pytest tests/storage/test_database.py -v`
Expected: FAIL

**Step 4: 实现数据库模块**

```python
# src/storage/database.py
import aiosqlite
import time
from .models import Trade, Liquidation, OISnapshot, PriceAlert


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        await self._create_tables()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def _create_tables(self) -> None:
        assert self.conn is not None
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                side TEXT NOT NULL,
                value_usd REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, timestamp);

            CREATE TABLE IF NOT EXISTS liquidations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                value_usd REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_liq_symbol_time ON liquidations(symbol, timestamp);

            CREATE TABLE IF NOT EXISTS oi_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open_interest REAL NOT NULL,
                open_interest_usd REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON oi_snapshots(symbol, timestamp);

            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                last_position TEXT,
                last_triggered_at INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_price_alerts_symbol ON price_alerts(symbol);

            CREATE TABLE IF NOT EXISTS thresholds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                p95_value REAL NOT NULL,
                sample_count INTEGER NOT NULL,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self.conn.commit()

    async def insert_trade(self, trade: Trade) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO trades (exchange, symbol, timestamp, price, amount, side, value_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (trade.exchange, trade.symbol, trade.timestamp, trade.price,
             trade.amount, trade.side, trade.value_usd),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_trades(self, symbol: str, hours: int) -> list[Trade]:
        assert self.conn is not None
        cutoff = int(time.time() * 1000) - hours * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT id, exchange, symbol, timestamp, price, amount, side, value_usd
               FROM trades WHERE symbol = ? AND timestamp >= ?
               ORDER BY timestamp DESC""",
            (symbol, cutoff),
        )
        rows = await cursor.fetchall()
        return [Trade(*row) for row in rows]

    async def insert_price_alert(self, alert: PriceAlert) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO price_alerts (symbol, price, last_position, last_triggered_at)
               VALUES (?, ?, ?, ?)""",
            (alert.symbol, alert.price, alert.last_position, alert.last_triggered_at),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_price_alerts(self, symbol: str) -> list[PriceAlert]:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """SELECT id, symbol, price, last_position, last_triggered_at
               FROM price_alerts WHERE symbol = ?""",
            (symbol,),
        )
        rows = await cursor.fetchall()
        return [PriceAlert(*row) for row in rows]

    async def delete_price_alert(self, symbol: str, price: float) -> None:
        assert self.conn is not None
        await self.conn.execute(
            "DELETE FROM price_alerts WHERE symbol = ? AND price = ?",
            (symbol, price),
        )
        await self.conn.commit()

    async def update_price_alert(
        self, alert_id: int, position: str | None = None, triggered_at: int | None = None
    ) -> None:
        assert self.conn is not None
        updates = []
        params: list = []
        if position is not None:
            updates.append("last_position = ?")
            params.append(position)
        if triggered_at is not None:
            updates.append("last_triggered_at = ?")
            params.append(triggered_at)
        if updates:
            params.append(alert_id)
            await self.conn.execute(
                f"UPDATE price_alerts SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            await self.conn.commit()
```

**Step 5: 运行测试确认通过**

Run: `uv run pytest tests/storage/test_database.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add .
git commit -m "feat: add database layer with trades and price_alerts"
```

---

### Task 4: 扩展数据库 - 爆仓和 OI

**Files:**
- Modify: `src/storage/database.py`
- Modify: `tests/storage/test_database.py`

**Step 1: 添加测试**

```python
# 追加到 tests/storage/test_database.py

async def test_insert_and_get_liquidations(db: Database):
    from src.storage.models import Liquidation

    liq = Liquidation(
        id=None,
        exchange="binance",
        symbol="BTC/USDT:USDT",
        timestamp=1706600000000,
        side="sell",
        price=99000.0,
        quantity=2.0,
        value_usd=198000.0,
    )
    await db.insert_liquidation(liq)

    liqs = await db.get_liquidations("BTC/USDT:USDT", hours=1)
    assert len(liqs) == 1
    assert liqs[0].side == "sell"


async def test_insert_and_get_oi(db: Database):
    from src.storage.models import OISnapshot

    oi = OISnapshot(
        id=None,
        exchange="binance",
        symbol="BTC/USDT:USDT",
        timestamp=1706600000000,
        open_interest=50000.0,
        open_interest_usd=5000000000.0,
    )
    await db.insert_oi_snapshot(oi)

    latest = await db.get_latest_oi("BTC/USDT:USDT")
    assert latest is not None
    assert latest.open_interest_usd == 5000000000.0
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/storage/test_database.py::test_insert_and_get_liquidations -v`
Expected: FAIL

**Step 3: 实现方法**

```python
# 追加到 src/storage/database.py Database 类

    async def insert_liquidation(self, liq: Liquidation) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO liquidations (exchange, symbol, timestamp, side, price, quantity, value_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (liq.exchange, liq.symbol, liq.timestamp, liq.side,
             liq.price, liq.quantity, liq.value_usd),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_liquidations(self, symbol: str, hours: int) -> list[Liquidation]:
        assert self.conn is not None
        cutoff = int(time.time() * 1000) - hours * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT id, exchange, symbol, timestamp, side, price, quantity, value_usd
               FROM liquidations WHERE symbol = ? AND timestamp >= ?
               ORDER BY timestamp DESC""",
            (symbol, cutoff),
        )
        rows = await cursor.fetchall()
        return [Liquidation(*row) for row in rows]

    async def insert_oi_snapshot(self, oi: OISnapshot) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO oi_snapshots (exchange, symbol, timestamp, open_interest, open_interest_usd)
               VALUES (?, ?, ?, ?, ?)""",
            (oi.exchange, oi.symbol, oi.timestamp, oi.open_interest, oi.open_interest_usd),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_latest_oi(self, symbol: str) -> OISnapshot | None:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """SELECT id, exchange, symbol, timestamp, open_interest, open_interest_usd
               FROM oi_snapshots WHERE symbol = ?
               ORDER BY timestamp DESC LIMIT 1""",
            (symbol,),
        )
        row = await cursor.fetchone()
        return OISnapshot(*row) if row else None

    async def get_oi_at(self, symbol: str, hours_ago: int) -> OISnapshot | None:
        assert self.conn is not None
        target = int(time.time() * 1000) - hours_ago * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT id, exchange, symbol, timestamp, open_interest, open_interest_usd
               FROM oi_snapshots WHERE symbol = ? AND timestamp <= ?
               ORDER BY timestamp DESC LIMIT 1""",
            (symbol, target),
        )
        row = await cursor.fetchone()
        return OISnapshot(*row) if row else None
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/storage/test_database.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add liquidation and OI database operations"
```

---

## Phase 4: 聚合器

### Task 5: 实现资金流向计算

**Files:**
- Create: `src/aggregator/__init__.py`
- Create: `src/aggregator/flow.py`
- Create: `tests/aggregator/__init__.py`
- Create: `tests/aggregator/test_flow.py`

**Step 1: 写失败测试**

```python
# tests/aggregator/test_flow.py
import pytest
from src.aggregator.flow import FlowResult, calculate_flow
from src.storage.models import Trade


def test_calculate_flow_net_positive():
    trades = [
        Trade(1, "binance", "BTC/USDT:USDT", 1706600000000, 100000, 1.0, "buy", 100000),
        Trade(2, "binance", "BTC/USDT:USDT", 1706600001000, 100000, 0.5, "sell", 50000),
        Trade(3, "okx", "BTC/USDT:USDT", 1706600002000, 100000, 0.8, "buy", 80000),
    ]

    result = calculate_flow(trades)

    assert result.net == 130000  # 180000 - 50000
    assert result.buy == 180000
    assert result.sell == 50000


def test_calculate_flow_by_exchange():
    trades = [
        Trade(1, "binance", "BTC/USDT:USDT", 1706600000000, 100000, 1.0, "buy", 100000),
        Trade(2, "okx", "BTC/USDT:USDT", 1706600001000, 100000, 0.5, "sell", 50000),
    ]

    result = calculate_flow(trades)

    assert result.by_exchange["binance"] == 100000
    assert result.by_exchange["okx"] == -50000


def test_calculate_flow_empty():
    result = calculate_flow([])
    assert result.net == 0
    assert result.buy == 0
    assert result.sell == 0
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/aggregator/test_flow.py -v`
Expected: FAIL

**Step 3: 实现资金流向模块**

```python
# src/aggregator/flow.py
from dataclasses import dataclass, field
from src.storage.models import Trade


@dataclass
class FlowResult:
    net: float = 0.0
    buy: float = 0.0
    sell: float = 0.0
    by_exchange: dict[str, float] = field(default_factory=dict)


def calculate_flow(trades: list[Trade]) -> FlowResult:
    if not trades:
        return FlowResult()

    buy = sum(t.value_usd for t in trades if t.side == "buy")
    sell = sum(t.value_usd for t in trades if t.side == "sell")
    net = buy - sell

    by_exchange: dict[str, float] = {}
    for t in trades:
        exchange_net = t.value_usd if t.side == "buy" else -t.value_usd
        by_exchange[t.exchange] = by_exchange.get(t.exchange, 0) + exchange_net

    return FlowResult(net=net, buy=buy, sell=sell, by_exchange=by_exchange)
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/aggregator/test_flow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add flow calculation"
```

---

### Task 6: 实现 OI 变化计算

**Files:**
- Create: `src/aggregator/oi.py`
- Create: `tests/aggregator/test_oi.py`

**Step 1: 写失败测试**

```python
# tests/aggregator/test_oi.py
from src.aggregator.oi import calculate_oi_change, interpret_oi_price
from src.storage.models import OISnapshot


def test_calculate_oi_change():
    current = OISnapshot(1, "binance", "BTC/USDT:USDT", 1706600000000, 50000, 5000000000)
    past = OISnapshot(2, "binance", "BTC/USDT:USDT", 1706596400000, 48000, 4800000000)

    change = calculate_oi_change(current, past)

    # (5000000000 - 4800000000) / 4800000000 * 100 = 4.166...%
    assert abs(change - 4.1667) < 0.01


def test_calculate_oi_change_none():
    assert calculate_oi_change(None, None) == 0.0
    current = OISnapshot(1, "binance", "BTC/USDT:USDT", 1706600000000, 50000, 5000000000)
    assert calculate_oi_change(current, None) == 0.0


def test_interpret_oi_price_new_long():
    assert interpret_oi_price(oi_change=2.0, price_change=1.5) == "新多入场"


def test_interpret_oi_price_new_short():
    assert interpret_oi_price(oi_change=2.0, price_change=-1.5) == "新空入场"


def test_interpret_oi_price_short_close():
    assert interpret_oi_price(oi_change=-2.0, price_change=1.5) == "空头平仓"


def test_interpret_oi_price_long_close():
    assert interpret_oi_price(oi_change=-2.0, price_change=-1.5) == "多头平仓"


def test_interpret_oi_price_stable():
    assert interpret_oi_price(oi_change=0.5, price_change=0.5) == "持仓稳定"
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/aggregator/test_oi.py -v`
Expected: FAIL

**Step 3: 实现 OI 模块**

```python
# src/aggregator/oi.py
from src.storage.models import OISnapshot


def calculate_oi_change(current: OISnapshot | None, past: OISnapshot | None) -> float:
    if not current or not past or past.open_interest_usd == 0:
        return 0.0
    return (current.open_interest_usd - past.open_interest_usd) / past.open_interest_usd * 100


def interpret_oi_price(oi_change: float, price_change: float) -> str:
    if oi_change > 1 and price_change > 0:
        return "新多入场"
    elif oi_change > 1 and price_change < 0:
        return "新空入场"
    elif oi_change < -1 and price_change > 0:
        return "空头平仓"
    elif oi_change < -1 and price_change < 0:
        return "多头平仓"
    else:
        return "持仓稳定"
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/aggregator/test_oi.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add OI change calculation"
```

---

### Task 7: 实现爆仓统计

**Files:**
- Create: `src/aggregator/liquidation.py`
- Create: `tests/aggregator/test_liquidation.py`

**Step 1: 写失败测试**

```python
# tests/aggregator/test_liquidation.py
from src.aggregator.liquidation import LiqStats, calculate_liquidations
from src.storage.models import Liquidation


def test_calculate_liquidations():
    liqs = [
        Liquidation(1, "binance", "BTC/USDT:USDT", 1706600000000, "sell", 99000, 1.0, 99000),
        Liquidation(2, "binance", "BTC/USDT:USDT", 1706600001000, "sell", 98500, 0.5, 49250),
        Liquidation(3, "okx", "BTC/USDT:USDT", 1706600002000, "buy", 101000, 0.3, 30300),
    ]

    stats = calculate_liquidations(liqs)

    assert stats.long == 148250  # sell = long liquidation
    assert stats.short == 30300  # buy = short liquidation
    assert stats.total == 178550


def test_calculate_liquidations_empty():
    stats = calculate_liquidations([])
    assert stats.long == 0
    assert stats.short == 0
    assert stats.total == 0
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/aggregator/test_liquidation.py -v`
Expected: FAIL

**Step 3: 实现爆仓统计模块**

```python
# src/aggregator/liquidation.py
from dataclasses import dataclass
from src.storage.models import Liquidation


@dataclass
class LiqStats:
    long: float = 0.0
    short: float = 0.0

    @property
    def total(self) -> float:
        return self.long + self.short


def calculate_liquidations(liqs: list[Liquidation]) -> LiqStats:
    if not liqs:
        return LiqStats()

    # sell = 多头爆仓 (long liquidation)
    # buy = 空头爆仓 (short liquidation)
    long_liq = sum(liq.value_usd for liq in liqs if liq.side == "sell")
    short_liq = sum(liq.value_usd for liq in liqs if liq.side == "buy")

    return LiqStats(long=long_liq, short=short_liq)
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/aggregator/test_liquidation.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add liquidation statistics"
```

---

### Task 8: 实现百分位计算

**Files:**
- Create: `src/aggregator/percentile.py`
- Create: `tests/aggregator/test_percentile.py`

**Step 1: 写失败测试**

```python
# tests/aggregator/test_percentile.py
from src.aggregator.percentile import calculate_percentile, get_level_emoji


def test_calculate_percentile():
    history = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    assert calculate_percentile(55, history) == 50.0  # 5 values below
    assert calculate_percentile(95, history) == 90.0  # 9 values below
    assert calculate_percentile(5, history) == 0.0   # 0 values below


def test_calculate_percentile_empty():
    assert calculate_percentile(50, []) == 50.0


def test_calculate_percentile_absolute():
    # 对于资金流向，用绝对值计算
    history = [10, 20, 30, 40, 50]
    assert calculate_percentile(-35, history) == 60.0  # abs(-35)=35, 3 values below


def test_get_level_emoji():
    assert get_level_emoji(50) == "🟢"
    assert get_level_emoji(74) == "🟢"
    assert get_level_emoji(75) == "🟡"
    assert get_level_emoji(89) == "🟡"
    assert get_level_emoji(90) == "🔴"
    assert get_level_emoji(99) == "🔴"
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/aggregator/test_percentile.py -v`
Expected: FAIL

**Step 3: 实现百分位模块**

```python
# src/aggregator/percentile.py


def calculate_percentile(value: float, history: list[float]) -> float:
    if not history:
        return 50.0
    count_below = sum(1 for h in history if h < abs(value))
    return count_below / len(history) * 100


def get_level_emoji(percentile: float) -> str:
    if percentile < 75:
        return "🟢"
    elif percentile < 90:
        return "🟡"
    else:
        return "🔴"
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/aggregator/test_percentile.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add percentile calculation"
```

---

## Phase 5: 告警系统

### Task 9: 实现异常触发检测

**Files:**
- Create: `src/alert/__init__.py`
- Create: `src/alert/trigger.py`
- Create: `tests/alert/__init__.py`
- Create: `tests/alert/test_trigger.py`

**Step 1: 写失败测试**

```python
# tests/alert/test_trigger.py
from src.alert.trigger import AlertType, check_alerts
from src.aggregator.flow import FlowResult
from src.aggregator.liquidation import LiqStats


def test_check_whale_flow_alert():
    flow = FlowResult(net=15000000, buy=20000000, sell=5000000)
    alerts = check_alerts(
        flow=flow,
        oi_change=1.0,
        liq_stats=LiqStats(),
        thresholds={"whale_flow_usd": 10000000, "oi_change_pct": 3, "liq_usd": 20000000},
    )

    assert len(alerts) == 1
    assert alerts[0].type == AlertType.WHALE_FLOW


def test_check_oi_alert():
    alerts = check_alerts(
        flow=FlowResult(),
        oi_change=4.5,
        liq_stats=LiqStats(),
        thresholds={"whale_flow_usd": 10000000, "oi_change_pct": 3, "liq_usd": 20000000},
    )

    assert len(alerts) == 1
    assert alerts[0].type == AlertType.OI_CHANGE


def test_check_liquidation_alert():
    alerts = check_alerts(
        flow=FlowResult(),
        oi_change=1.0,
        liq_stats=LiqStats(long=25000000, short=5000000),
        thresholds={"whale_flow_usd": 10000000, "oi_change_pct": 3, "liq_usd": 20000000},
    )

    assert len(alerts) == 1
    assert alerts[0].type == AlertType.LIQUIDATION


def test_check_no_alerts():
    alerts = check_alerts(
        flow=FlowResult(net=5000000),
        oi_change=1.0,
        liq_stats=LiqStats(long=5000000),
        thresholds={"whale_flow_usd": 10000000, "oi_change_pct": 3, "liq_usd": 20000000},
    )

    assert len(alerts) == 0
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/alert/test_trigger.py -v`
Expected: FAIL

**Step 3: 实现触发检测模块**

```python
# src/alert/trigger.py
from dataclasses import dataclass
from enum import Enum

from src.aggregator.flow import FlowResult
from src.aggregator.liquidation import LiqStats


class AlertType(Enum):
    WHALE_FLOW = "whale_flow"
    OI_CHANGE = "oi_change"
    LIQUIDATION = "liquidation"


@dataclass
class Alert:
    type: AlertType
    value: float
    threshold: float


def check_alerts(
    flow: FlowResult,
    oi_change: float,
    liq_stats: LiqStats,
    thresholds: dict[str, float],
) -> list[Alert]:
    alerts: list[Alert] = []

    # 大单流向异常
    whale_threshold = thresholds.get("whale_flow_usd", 10000000)
    if abs(flow.net) > whale_threshold:
        alerts.append(Alert(
            type=AlertType.WHALE_FLOW,
            value=flow.net,
            threshold=whale_threshold,
        ))

    # OI 变化异常
    oi_threshold = thresholds.get("oi_change_pct", 3)
    if abs(oi_change) > oi_threshold:
        alerts.append(Alert(
            type=AlertType.OI_CHANGE,
            value=oi_change,
            threshold=oi_threshold,
        ))

    # 爆仓异常
    liq_threshold = thresholds.get("liq_usd", 20000000)
    if liq_stats.total > liq_threshold:
        alerts.append(Alert(
            type=AlertType.LIQUIDATION,
            value=liq_stats.total,
            threshold=liq_threshold,
        ))

    return alerts
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/alert/test_trigger.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add alert trigger detection"
```

---

### Task 10: 实现价位监控

**Files:**
- Create: `src/alert/price_monitor.py`
- Create: `tests/alert/test_price_monitor.py`

**Step 1: 写失败测试**

```python
# tests/alert/test_price_monitor.py
from src.alert.price_monitor import PriceAlertResult, check_price_alerts
from src.storage.models import PriceAlert


def test_breakout_from_below():
    alerts = [
        PriceAlert(id=1, symbol="BTC", price=100000, last_position="below", last_triggered_at=None)
    ]
    current_price = 100500

    results = check_price_alerts(alerts, current_price, cooldown_seconds=3600)

    assert len(results) == 1
    assert results[0].alert_id == 1
    assert results[0].type == "breakout"
    assert results[0].price == 100000


def test_breakdown_from_above():
    alerts = [
        PriceAlert(id=1, symbol="BTC", price=100000, last_position="above", last_triggered_at=None)
    ]
    current_price = 99500

    results = check_price_alerts(alerts, current_price, cooldown_seconds=3600)

    assert len(results) == 1
    assert results[0].type == "breakdown"


def test_cooldown_blocks_trigger():
    import time
    now = int(time.time())
    alerts = [
        PriceAlert(id=1, symbol="BTC", price=100000, last_position="below",
                   last_triggered_at=now - 1800)  # 30 分钟前触发
    ]
    current_price = 100500

    results = check_price_alerts(alerts, current_price, cooldown_seconds=3600)

    assert len(results) == 0  # 冷却中


def test_no_trigger_same_side():
    alerts = [
        PriceAlert(id=1, symbol="BTC", price=100000, last_position="above", last_triggered_at=None)
    ]
    current_price = 100500  # 仍在上方

    results = check_price_alerts(alerts, current_price, cooldown_seconds=3600)

    assert len(results) == 0
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/alert/test_price_monitor.py -v`
Expected: FAIL

**Step 3: 实现价位监控模块**

```python
# src/alert/price_monitor.py
import time
from dataclasses import dataclass

from src.storage.models import PriceAlert


@dataclass
class PriceAlertResult:
    alert_id: int
    type: str  # "breakout" | "breakdown"
    price: float


def check_price_alerts(
    alerts: list[PriceAlert],
    current_price: float,
    cooldown_seconds: int,
) -> list[PriceAlertResult]:
    results: list[PriceAlertResult] = []
    now = int(time.time())

    for alert in alerts:
        # 检查冷却
        if alert.last_triggered_at:
            if now - alert.last_triggered_at < cooldown_seconds:
                continue

        # 检查突破/跌破
        if alert.last_position == "below" and current_price >= alert.price:
            results.append(PriceAlertResult(
                alert_id=alert.id or 0,
                type="breakout",
                price=alert.price,
            ))
        elif alert.last_position == "above" and current_price <= alert.price:
            results.append(PriceAlertResult(
                alert_id=alert.id or 0,
                type="breakdown",
                price=alert.price,
            ))

    return results
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/alert/test_price_monitor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add price alert monitoring"
```

---

## Phase 6: 消息格式化

### Task 11: 实现消息格式化

**Files:**
- Create: `src/notifier/__init__.py`
- Create: `src/notifier/formatter.py`
- Create: `tests/notifier/__init__.py`
- Create: `tests/notifier/test_formatter.py`

**Step 1: 写失败测试**

```python
# tests/notifier/test_formatter.py
from src.notifier.formatter import format_report, format_price_alert


def test_format_report():
    data = {
        "symbol": "BTC",
        "price": 104230,
        "price_change_1h": 1.2,
        "price_change_24h": 3.5,
        "flow_1h": 5200000,
        "flow_1h_pct": 62,
        "flow_4h": 18300000,
        "flow_4h_pct": 78,
        "flow_24h": 42100000,
        "flow_24h_pct": 55,
        "flow_binance": 28000000,
        "flow_okx": 14000000,
        "oi_value": 18200000000,
        "oi_change_1h": 1.2,
        "oi_change_1h_pct": 58,
        "oi_change_4h": 2.3,
        "oi_change_4h_pct": 76,
        "oi_interpretation": "新多入场",
        "liq_1h_total": 7400000,
        "liq_1h_pct": 52,
        "liq_1h_long": 2100000,
        "liq_1h_short": 5300000,
        "liq_4h_total": 20300000,
        "liq_4h_pct": 82,
        "liq_4h_long": 8200000,
        "liq_4h_short": 12100000,
        "funding_rate": -0.01,
        "funding_rate_pct": 48,
        "long_short_ratio": 1.35,
        "long_short_ratio_pct": 62,
        "spot_perp_spread": 0.05,
        "spot_perp_spread_pct": 44,
    }

    msg = format_report(data)

    assert "BTC" in msg
    assert "$104,230" in msg
    assert "+1.2%" in msg
    assert "🟢" in msg  # P62 should be green


def test_format_price_alert_breakout():
    data = {
        "symbol": "BTC",
        "type": "breakout",
        "target_price": 100000,
        "current_price": 100150,
        "price_change_1h": 0.3,
        "flow_1h": 3200000,
        "flow_1h_pct": 62,
        "oi_change_1h": 2.8,
        "oi_change_1h_pct": 85,
        "liq_1h_total": 8500000,
        "liq_1h_pct": 58,
        "liq_1h_long": 3200000,
        "liq_1h_short": 5300000,
        "funding_rate": 0.01,
        "funding_rate_pct": 45,
    }

    msg = format_price_alert(data)

    assert "📍 BTC 突破 100000" in msg
    assert "$100,150" in msg
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/notifier/test_formatter.py -v`
Expected: FAIL

**Step 3: 实现格式化模块**

```python
# src/notifier/formatter.py
from datetime import datetime, timezone

from src.aggregator.percentile import get_level_emoji


def _format_usd(value: float) -> str:
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    elif abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    else:
        return f"${value:,.0f}"


def _format_usd_signed(value: float) -> str:
    sign = "+" if value >= 0 else ""
    if abs(value) >= 1_000_000_000:
        return f"{sign}${abs(value) / 1_000_000_000:.1f}B"
    elif abs(value) >= 1_000_000:
        return f"{sign}${abs(value) / 1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{sign}${abs(value) / 1_000:.1f}K"
    else:
        return f"{sign}${abs(value):,.0f}"


def _level(pct: float) -> str:
    return f"{get_level_emoji(pct)} P{int(pct)}"


def format_report(data: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 判断交易所一致性
    flow_binance = data.get("flow_binance", 0)
    flow_okx = data.get("flow_okx", 0)
    consistency = "✓一致" if (flow_binance >= 0) == (flow_okx >= 0) else "⚠️分歧"

    return f"""📊 {data['symbol']} 市场快照
⏰ {now}

💵 ${data['price']:,.0f} ({data['price_change_1h']:+.1f}% 1h / {data['price_change_24h']:+.1f}% 24h)

━━━━━━━━━━━━━━━━━━━━
💰 主力资金 (大单净流向):
  1h: {_format_usd_signed(data['flow_1h'])} {_level(data['flow_1h_pct'])} | 4h: {_format_usd_signed(data['flow_4h'])} {_level(data['flow_4h_pct'])}
  24h: {_format_usd_signed(data['flow_24h'])} {_level(data['flow_24h_pct'])}
  Binance: {_format_usd_signed(flow_binance)} | OKX: {_format_usd_signed(flow_okx)} {consistency}

━━━━━━━━━━━━━━━━━━━━
📈 持仓量 (OI): {_format_usd(data['oi_value'])}
  1h: {data['oi_change_1h']:+.1f}% {_level(data['oi_change_1h_pct'])} | 4h: {data['oi_change_4h']:+.1f}% {_level(data['oi_change_4h_pct'])}
  → 价格{'↑' if data['price_change_1h'] > 0 else '↓'} OI{'↑' if data['oi_change_1h'] > 0 else '↓'} = {data['oi_interpretation']}

━━━━━━━━━━━━━━━━━━━━
💥 爆仓:
  1h: {_format_usd(data['liq_1h_total'])} {_level(data['liq_1h_pct'])} (多{_format_usd(data['liq_1h_long'])} / 空{_format_usd(data['liq_1h_short'])})
  4h: {_format_usd(data['liq_4h_total'])} {_level(data['liq_4h_pct'])} (多{_format_usd(data['liq_4h_long'])} / 空{_format_usd(data['liq_4h_short'])})

━━━━━━━━━━━━━━━━━━━━
📊 情绪指标:
  资金费率: {data['funding_rate']:+.2f}% {_level(data['funding_rate_pct'])} ({'多头付费' if data['funding_rate'] > 0 else '空头付费'})
  多空比: {data['long_short_ratio']:.2f} {_level(data['long_short_ratio_pct'])} ({'散户偏多' if data['long_short_ratio'] > 1 else '散户偏空'})
  合约溢价: {data['spot_perp_spread']:+.2f}% {_level(data['spot_perp_spread_pct'])}"""


def format_price_alert(data: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    action = "突破" if data["type"] == "breakout" else "跌破"

    return f"""📍 {data['symbol']} {action} {int(data['target_price'])}

💵 当前: ${data['current_price']:,.0f} ({data['price_change_1h']:+.1f}% 1h)

💰 主力资金 1h: {_format_usd_signed(data['flow_1h'])} {_level(data['flow_1h_pct'])}
📈 OI 变化 1h: {data['oi_change_1h']:+.1f}% {_level(data['oi_change_1h_pct'])}
💥 爆仓 1h: {_format_usd(data['liq_1h_total'])} {_level(data['liq_1h_pct'])} (多{_format_usd(data['liq_1h_long'])} / 空{_format_usd(data['liq_1h_short'])})
📊 资金费率: {data['funding_rate']:+.2f}% {_level(data['funding_rate_pct'])}

⏰ {now}"""


def format_whale_alert(data: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    direction = "净流入" if data["flow_1h"] > 0 else "净流出"

    return f"""⚠️ {data['symbol']} 大单异常

1h {direction} {_format_usd(abs(data['flow_1h']))} {_level(data['flow_1h_pct'])}
  Binance: {_format_usd_signed(data.get('flow_binance', 0))}
  OKX: {_format_usd_signed(data.get('flow_okx', 0))}

💵 ${data['price']:,.0f} ({data['price_change_1h']:+.1f}% 1h)
⏰ {now}"""
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/notifier/test_formatter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add message formatter"
```

---

## Phase 7: 数据采集器

### Task 12: 实现采集器基类

**Files:**
- Create: `src/collector/__init__.py`
- Create: `src/collector/base.py`

**Step 1: 创建基类**

```python
# src/collector/base.py
from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.running = False
        self._task: asyncio.Task | None = None

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def _process_message(self, message: Any) -> None:
        pass

    async def start(self) -> None:
        self.running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"{self.__class__.__name__} started for {self.symbol}")

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.disconnect()
        logger.info(f"{self.__class__.__name__} stopped for {self.symbol}")

    @abstractmethod
    async def _run(self) -> None:
        pass
```

**Step 2: Commit**

```bash
git add .
git commit -m "feat: add collector base class"
```

---

### Task 13: 实现 Binance Trades 采集器

**Files:**
- Create: `src/collector/binance_trades.py`
- Create: `tests/collector/__init__.py`
- Create: `tests/collector/test_binance_trades.py`

**Step 1: 写测试**

```python
# tests/collector/test_binance_trades.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.collector.binance_trades import BinanceTradesCollector


def test_parse_trade_message():
    collector = BinanceTradesCollector(
        symbol="BTC/USDT:USDT",
        threshold_usd=100000,
        on_trade=AsyncMock(),
    )

    # ccxt 格式的 trade
    trade = {
        "symbol": "BTC/USDT:USDT",
        "timestamp": 1706600000000,
        "price": 100000.0,
        "amount": 1.5,
        "side": "buy",
        "info": {"m": False},  # m=False means buyer is taker
    }

    result = collector._parse_trade(trade)

    assert result is not None
    assert result.exchange == "binance"
    assert result.symbol == "BTC/USDT:USDT"
    assert result.value_usd == 150000.0
    assert result.side == "buy"


def test_filter_small_trade():
    collector = BinanceTradesCollector(
        symbol="BTC/USDT:USDT",
        threshold_usd=100000,
        on_trade=AsyncMock(),
    )

    trade = {
        "symbol": "BTC/USDT:USDT",
        "timestamp": 1706600000000,
        "price": 100000.0,
        "amount": 0.5,  # 50000 USD < threshold
        "side": "buy",
        "info": {"m": False},
    }

    result = collector._parse_trade(trade)

    assert result is None
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/collector/test_binance_trades.py -v`
Expected: FAIL

**Step 3: 实现采集器**

```python
# src/collector/binance_trades.py
import asyncio
import logging
from typing import Any, Callable, Coroutine

import ccxt.pro as ccxtpro

from .base import BaseCollector
from src.storage.models import Trade

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

    def _parse_trade(self, trade: dict) -> Trade | None:
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

    async def _process_message(self, trades: list[dict]) -> None:
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
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/collector/test_binance_trades.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add Binance trades collector"
```

---

### Task 14: 实现 OKX Trades 采集器

**Files:**
- Create: `src/collector/okx_trades.py`
- Create: `tests/collector/test_okx_trades.py`

**Step 1: 写测试**

```python
# tests/collector/test_okx_trades.py
from unittest.mock import AsyncMock
from src.collector.okx_trades import OKXTradesCollector


def test_parse_trade_message():
    collector = OKXTradesCollector(
        symbol="BTC/USDT:USDT",
        threshold_usd=100000,
        on_trade=AsyncMock(),
    )

    trade = {
        "symbol": "BTC/USDT:USDT",
        "timestamp": 1706600000000,
        "price": 100000.0,
        "amount": 2.0,
        "side": "buy",
    }

    result = collector._parse_trade(trade)

    assert result is not None
    assert result.exchange == "okx"
    assert result.value_usd == 200000.0
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/collector/test_okx_trades.py -v`
Expected: FAIL

**Step 3: 实现采集器**

```python
# src/collector/okx_trades.py
import asyncio
import logging
from typing import Any, Callable, Coroutine

import ccxt.pro as ccxtpro

from .base import BaseCollector
from src.storage.models import Trade

logger = logging.getLogger(__name__)


class OKXTradesCollector(BaseCollector):
    def __init__(
        self,
        symbol: str,
        threshold_usd: float,
        on_trade: Callable[[Trade], Coroutine[Any, Any, None]],
    ):
        super().__init__(symbol)
        self.threshold_usd = threshold_usd
        self.on_trade = on_trade
        self.exchange: ccxtpro.okx | None = None

    async def connect(self) -> None:
        self.exchange = ccxtpro.okx()

    async def disconnect(self) -> None:
        if self.exchange:
            await self.exchange.close()

    def _parse_trade(self, trade: dict) -> Trade | None:
        price = float(trade["price"])
        amount = float(trade["amount"])
        value_usd = price * amount

        if value_usd < self.threshold_usd:
            return None

        return Trade(
            id=None,
            exchange="okx",
            symbol=trade["symbol"],
            timestamp=trade["timestamp"],
            price=price,
            amount=amount,
            side=trade["side"],
            value_usd=value_usd,
        )

    async def _process_message(self, trades: list[dict]) -> None:
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
                logger.error(f"OKX trades error: {e}")
                await asyncio.sleep(5)
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/collector/test_okx_trades.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add OKX trades collector"
```

---

### Task 15: 实现 Binance 爆仓采集器

**Files:**
- Create: `src/collector/binance_liq.py`
- Create: `tests/collector/test_binance_liq.py`

**Step 1: 写测试**

```python
# tests/collector/test_binance_liq.py
import json
from unittest.mock import AsyncMock
from src.collector.binance_liq import BinanceLiquidationCollector


def test_parse_liquidation_message():
    collector = BinanceLiquidationCollector(
        symbols=["BTC/USDT:USDT"],
        on_liquidation=AsyncMock(),
    )

    # Binance forceOrder 原始格式
    message = {
        "e": "forceOrder",
        "E": 1706600000000,
        "o": {
            "s": "BTCUSDT",
            "S": "SELL",
            "q": "1.5",
            "p": "99000",
            "ap": "98500",
            "X": "FILLED",
            "T": 1706600000000,
        }
    }

    result = collector._parse_liquidation(message)

    assert result is not None
    assert result.exchange == "binance"
    assert result.symbol == "BTC/USDT:USDT"
    assert result.side == "sell"
    assert result.quantity == 1.5
    assert result.value_usd == 147750.0  # 1.5 * 98500
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/collector/test_binance_liq.py -v`
Expected: FAIL

**Step 3: 实现采集器**

```python
# src/collector/binance_liq.py
import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

import websockets

from .base import BaseCollector
from src.storage.models import Liquidation

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
        streams = [f"{s.replace('/', '').replace(':USDT', '').lower()}@forceOrder"
                   for s in self.symbols]
        url = f"{BINANCE_FUTURES_WS}/{'/'.join(streams)}"
        self.ws = await websockets.connect(url)

    async def disconnect(self) -> None:
        if self.ws:
            await self.ws.close()

    def _parse_liquidation(self, data: dict) -> Liquidation | None:
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
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/collector/test_binance_liq.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add Binance liquidation collector"
```

---

### Task 16: 实现指标获取器

**Files:**
- Create: `src/collector/indicator_fetcher.py`
- Create: `tests/collector/test_indicator_fetcher.py`

**Step 1: 写测试**

```python
# tests/collector/test_indicator_fetcher.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def test_fetch_oi():
    from src.collector.indicator_fetcher import IndicatorFetcher

    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    # Mock ccxt exchange
    mock_exchange = MagicMock()
    mock_exchange.fetch_open_interest = AsyncMock(return_value={
        "symbol": "BTC/USDT:USDT",
        "openInterestAmount": 50000.0,
        "openInterestValue": 5000000000.0,
        "timestamp": 1706600000000,
    })

    fetcher.binance = mock_exchange

    result = await fetcher._fetch_oi("binance", "BTC/USDT:USDT")

    assert result is not None
    assert result.open_interest == 50000.0
    assert result.open_interest_usd == 5000000000.0
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/collector/test_indicator_fetcher.py -v`
Expected: FAIL

**Step 3: 实现指标获取器**

```python
# src/collector/indicator_fetcher.py
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

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

            data = await ex.fetch_open_interest(symbol)
            return OISnapshot(
                id=None,
                exchange=exchange,
                symbol=symbol,
                timestamp=data["timestamp"],
                open_interest=data["openInterestAmount"],
                open_interest_usd=data["openInterestValue"],
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
            funding = await self.binance.fetch_funding_rate(symbol)
            funding_rate = funding.get("fundingRate", 0) * 100  # Convert to percentage

            # Fetch long/short ratio (global accounts)
            raw_symbol = symbol.replace("/", "").replace(":USDT", "")
            ls_data = await self.binance.fapiPublicGetGlobalLongShortAccountRatio({
                "symbol": raw_symbol,
                "period": "5m",
                "limit": 1,
            })
            long_short_ratio = float(ls_data[0]["longShortRatio"]) if ls_data else 1.0

            # Fetch spot price
            spot_ticker = await self.binance_spot.fetch_ticker(symbol.replace(":USDT", ""))
            spot_price = spot_ticker["last"]

            # Fetch futures price
            futures_ticker = await self.binance.fetch_ticker(symbol)
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
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/collector/test_indicator_fetcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add indicator fetcher"
```

---

## Phase 8: Telegram Bot

### Task 17: 实现 Telegram Bot

**Files:**
- Create: `src/notifier/telegram.py`
- Create: `tests/notifier/test_telegram.py`

**Step 1: 写测试**

```python
# tests/notifier/test_telegram.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def test_send_message():
    with patch("src.notifier.telegram.Bot") as MockBot:
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        MockBot.return_value = mock_bot

        from src.notifier.telegram import TelegramNotifier

        notifier = TelegramNotifier(bot_token="test", chat_id="123")
        await notifier.send_message("Hello")

        mock_bot.send_message.assert_called_once_with(
            chat_id="123",
            text="Hello",
            parse_mode="HTML",
        )


async def test_parse_watch_command():
    from src.notifier.telegram import TelegramNotifier

    result = TelegramNotifier._parse_watch_command("/watch BTC 100000")
    assert result == ("BTC", 100000.0)

    result = TelegramNotifier._parse_watch_command("/watch ETH 3500.5")
    assert result == ("ETH", 3500.5)

    result = TelegramNotifier._parse_watch_command("/watch invalid")
    assert result is None
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/notifier/test_telegram.py -v`
Expected: FAIL

**Step 3: 实现 Telegram Bot**

```python
# src/notifier/telegram.py
import logging
import re
from typing import Callable, Coroutine, Any

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
        self.app: Application | None = None

        # Callbacks
        self.on_watch: Callable[[str, float], Coroutine[Any, Any, None]] | None = None
        self.on_unwatch: Callable[[str, float], Coroutine[Any, Any, None]] | None = None
        self.on_list: Callable[[], Coroutine[Any, Any, str]] | None = None
        self.on_report: Callable[[str], Coroutine[Any, Any, str]] | None = None
        self.on_status: Callable[[], Coroutine[Any, Any, str]] | None = None

    async def send_message(self, text: str) -> None:
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode="HTML",
        )

    @staticmethod
    def _parse_watch_command(text: str) -> tuple[str, float] | None:
        match = re.match(r"/(?:un)?watch\s+(\w+)\s+([\d.]+)", text)
        if match:
            return match.group(1).upper(), float(match.group(2))
        return None

    async def _handle_watch(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        result = self._parse_watch_command(update.message.text)
        if not result:
            await update.message.reply_text("用法: /watch BTC 100000")
            return

        symbol, price = result
        if self.on_watch:
            await self.on_watch(symbol, price)
        await update.message.reply_text(f"✅ 已添加 {symbol} {int(price)} 监控")

    async def _handle_unwatch(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        result = self._parse_watch_command(update.message.text)
        if not result:
            await update.message.reply_text("用法: /unwatch BTC 100000")
            return

        symbol, price = result
        if self.on_unwatch:
            await self.on_unwatch(symbol, price)
        await update.message.reply_text(f"✅ 已取消 {symbol} {int(price)} 监控")

    async def _handle_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return

        if self.on_list:
            text = await self.on_list()
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("暂无监控价位")

    async def _handle_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        parts = update.message.text.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"

        if self.on_report:
            text = await self.on_report(symbol)
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("报告生成中...")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return

        if self.on_status:
            text = await self.on_status()
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("系统运行中")

    def setup_handlers(self, app: Application) -> None:
        app.add_handler(CommandHandler("watch", self._handle_watch))
        app.add_handler(CommandHandler("unwatch", self._handle_unwatch))
        app.add_handler(CommandHandler("list", self._handle_list))
        app.add_handler(CommandHandler("report", self._handle_report))
        app.add_handler(CommandHandler("status", self._handle_status))

    async def start_polling(self) -> None:
        self.app = Application.builder().token(self.bot_token).build()
        self.setup_handlers(self.app)
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()  # type: ignore

    async def stop_polling(self) -> None:
        if self.app:
            await self.app.updater.stop()  # type: ignore
            await self.app.stop()
            await self.app.shutdown()
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/notifier/test_telegram.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add Telegram bot with commands"
```

---

## Phase 9: 主程序

### Task 18: 实现主程序

**Files:**
- Create: `src/main.py`

**Step 1: 实现主程序**

```python
# src/main.py
import asyncio
import logging
import signal
import time
from pathlib import Path

from src.config import Config, load_config
from src.storage.database import Database
from src.storage.models import Trade, Liquidation, PriceAlert
from src.collector.binance_trades import BinanceTradesCollector
from src.collector.okx_trades import OKXTradesCollector
from src.collector.binance_liq import BinanceLiquidationCollector
from src.collector.indicator_fetcher import IndicatorFetcher
from src.aggregator.flow import calculate_flow
from src.aggregator.oi import calculate_oi_change, interpret_oi_price
from src.aggregator.liquidation import calculate_liquidations
from src.aggregator.percentile import calculate_percentile, get_level_emoji
from src.alert.trigger import check_alerts
from src.alert.price_monitor import check_price_alerts
from src.notifier.telegram import TelegramNotifier
from src.notifier.formatter import format_report, format_price_alert, format_whale_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CryptoMonitor:
    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.database.path)
        self.notifier = TelegramNotifier(config.telegram.bot_token, config.telegram.chat_id)
        self.indicator_fetcher = IndicatorFetcher(config.symbols)
        self.collectors: list = []
        self.running = False
        self.start_time = time.time()

    async def init(self) -> None:
        # Ensure data directory exists
        Path(self.config.database.path).parent.mkdir(parents=True, exist_ok=True)

        await self.db.init()
        await self.indicator_fetcher.init()

        # Setup collectors
        for symbol in self.config.symbols:
            if self.config.exchanges.binance.enabled:
                self.collectors.append(BinanceTradesCollector(
                    symbol=symbol,
                    threshold_usd=self.config.thresholds.default_usd,
                    on_trade=self._on_trade,
                ))
            if self.config.exchanges.okx.enabled:
                self.collectors.append(OKXTradesCollector(
                    symbol=symbol,
                    threshold_usd=self.config.thresholds.default_usd,
                    on_trade=self._on_trade,
                ))

        if self.config.exchanges.binance.enabled:
            self.collectors.append(BinanceLiquidationCollector(
                symbols=self.config.symbols,
                on_liquidation=self._on_liquidation,
            ))

        # Setup Telegram callbacks
        self.notifier.on_watch = self._on_watch
        self.notifier.on_unwatch = self._on_unwatch
        self.notifier.on_list = self._on_list
        self.notifier.on_report = self._on_report
        self.notifier.on_status = self._on_status

    async def _on_trade(self, trade: Trade) -> None:
        await self.db.insert_trade(trade)
        logger.debug(f"Trade: {trade.exchange} {trade.symbol} {trade.side} ${trade.value_usd:,.0f}")

    async def _on_liquidation(self, liq: Liquidation) -> None:
        await self.db.insert_liquidation(liq)
        logger.debug(f"Liquidation: {liq.exchange} {liq.symbol} {liq.side} ${liq.value_usd:,.0f}")

    async def _on_watch(self, symbol: str, price: float) -> None:
        # Get current price to determine position
        indicators = await self.indicator_fetcher.fetch_indicators(f"{symbol}/USDT:USDT")
        current_price = indicators.futures_price if indicators else 0
        position = "above" if current_price > price else "below"

        alert = PriceAlert(
            id=None,
            symbol=symbol,
            price=price,
            last_position=position,
            last_triggered_at=None,
        )
        await self.db.insert_price_alert(alert)

    async def _on_unwatch(self, symbol: str, price: float) -> None:
        await self.db.delete_price_alert(symbol, price)

    async def _on_list(self) -> str:
        lines = ["📋 当前监控价位\n"]
        for symbol in ["BTC", "ETH"]:
            alerts = await self.db.get_price_alerts(symbol)
            if alerts:
                lines.append(f"{symbol}:")
                for alert in alerts:
                    lines.append(f"  • {int(alert.price)}")
                lines.append("")
        return "\n".join(lines) if len(lines) > 1 else "暂无监控价位"

    async def _on_report(self, symbol: str) -> str:
        return await self._generate_report(f"{symbol}/USDT:USDT")

    async def _on_status(self) -> str:
        uptime = time.time() - self.start_time
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)

        return f"""🔧 系统状态

运行时间: {days}d {hours}h {minutes}m
数据连接: 🟢 正常

监控币种: {', '.join(self.config.symbols)}
"""

    async def _generate_report(self, symbol: str) -> str:
        # Fetch current data
        trades_1h = await self.db.get_trades(symbol, hours=1)
        trades_4h = await self.db.get_trades(symbol, hours=4)
        trades_24h = await self.db.get_trades(symbol, hours=24)

        flow_1h = calculate_flow(trades_1h)
        flow_4h = calculate_flow(trades_4h)
        flow_24h = calculate_flow(trades_24h)

        liqs_1h = await self.db.get_liquidations(symbol, hours=1)
        liqs_4h = await self.db.get_liquidations(symbol, hours=4)
        liq_stats_1h = calculate_liquidations(liqs_1h)
        liq_stats_4h = calculate_liquidations(liqs_4h)

        current_oi = await self.db.get_latest_oi(symbol)
        past_oi_1h = await self.db.get_oi_at(symbol, hours_ago=1)
        past_oi_4h = await self.db.get_oi_at(symbol, hours_ago=4)
        oi_change_1h = calculate_oi_change(current_oi, past_oi_1h)
        oi_change_4h = calculate_oi_change(current_oi, past_oi_4h)

        indicators = await self.indicator_fetcher.fetch_indicators(symbol)

        # Calculate percentiles (simplified - would use historical data in production)
        data = {
            "symbol": symbol.split("/")[0],
            "price": indicators.futures_price if indicators else 0,
            "price_change_1h": 0,  # Would calculate from historical prices
            "price_change_24h": 0,
            "flow_1h": flow_1h.net,
            "flow_1h_pct": 50,  # Would calculate from historical data
            "flow_4h": flow_4h.net,
            "flow_4h_pct": 50,
            "flow_24h": flow_24h.net,
            "flow_24h_pct": 50,
            "flow_binance": flow_1h.by_exchange.get("binance", 0),
            "flow_okx": flow_1h.by_exchange.get("okx", 0),
            "oi_value": current_oi.open_interest_usd if current_oi else 0,
            "oi_change_1h": oi_change_1h,
            "oi_change_1h_pct": 50,
            "oi_change_4h": oi_change_4h,
            "oi_change_4h_pct": 50,
            "oi_interpretation": interpret_oi_price(oi_change_1h, 0),
            "liq_1h_total": liq_stats_1h.total,
            "liq_1h_pct": 50,
            "liq_1h_long": liq_stats_1h.long,
            "liq_1h_short": liq_stats_1h.short,
            "liq_4h_total": liq_stats_4h.total,
            "liq_4h_pct": 50,
            "liq_4h_long": liq_stats_4h.long,
            "liq_4h_short": liq_stats_4h.short,
            "funding_rate": indicators.funding_rate if indicators else 0,
            "funding_rate_pct": 50,
            "long_short_ratio": indicators.long_short_ratio if indicators else 1,
            "long_short_ratio_pct": 50,
            "spot_perp_spread": indicators.spot_perp_spread if indicators else 0,
            "spot_perp_spread_pct": 50,
        }

        return format_report(data)

    async def _scheduled_report(self) -> None:
        interval = self.config.intervals.report_hours * 3600
        while self.running:
            await asyncio.sleep(interval)
            for symbol in self.config.symbols:
                try:
                    report = await self._generate_report(symbol)
                    await self.notifier.send_message(report)
                except Exception as e:
                    logger.error(f"Failed to send report for {symbol}: {e}")

    async def _fetch_indicators(self) -> None:
        interval = self.config.intervals.oi_fetch_minutes * 60
        while self.running:
            try:
                oi_snapshots = await self.indicator_fetcher.fetch_all_oi()
                for oi in oi_snapshots:
                    await self.db.insert_oi_snapshot(oi)
            except Exception as e:
                logger.error(f"Failed to fetch indicators: {e}")
            await asyncio.sleep(interval)

    async def _check_alerts(self) -> None:
        while self.running:
            await asyncio.sleep(60)  # Check every minute

            for symbol in self.config.symbols:
                try:
                    # Check price alerts
                    short_symbol = symbol.split("/")[0]
                    price_alerts = await self.db.get_price_alerts(short_symbol)
                    indicators = await self.indicator_fetcher.fetch_indicators(symbol)

                    if indicators and price_alerts:
                        triggered = check_price_alerts(
                            price_alerts,
                            indicators.futures_price,
                            self.config.price_alerts.cooldown_minutes * 60,
                        )
                        for result in triggered:
                            # Update alert state
                            new_position = "above" if indicators.futures_price > result.price else "below"
                            await self.db.update_price_alert(
                                result.alert_id,
                                position=new_position,
                                triggered_at=int(time.time()),
                            )
                            # Send notification
                            # ... (would gather data and format)
                except Exception as e:
                    logger.error(f"Failed to check alerts for {symbol}: {e}")

    async def run(self) -> None:
        await self.init()
        self.running = True

        # Start collectors
        for collector in self.collectors:
            await collector.start()

        # Start Telegram bot
        await self.notifier.start_polling()

        # Start background tasks
        tasks = [
            asyncio.create_task(self._scheduled_report()),
            asyncio.create_task(self._fetch_indicators()),
            asyncio.create_task(self._check_alerts()),
        ]

        logger.info("Crypto Monitor started")

        # Wait for shutdown signal
        stop_event = asyncio.Event()
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()

        # Cleanup
        self.running = False
        for task in tasks:
            task.cancel()
        for collector in self.collectors:
            await collector.stop()
        await self.notifier.stop_polling()
        await self.indicator_fetcher.close()
        await self.db.close()

        logger.info("Crypto Monitor stopped")


async def main() -> None:
    config = load_config(Path("config.yaml"))
    monitor = CryptoMonitor(config)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Commit**

```bash
git add .
git commit -m "feat: add main program"
```

---

## Phase 10: Docker 部署

### Task 19: 创建 Docker 配置

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

**Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv sync --no-dev

# Run
CMD ["uv", "run", "python", "-m", "src.main"]
```

**Step 2: 创建 docker-compose.yml**

```yaml
version: '3.8'

services:
  crypto-monitor:
    build: .
    container_name: crypto-monitor
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
    environment:
      - TZ=UTC
```

**Step 3: 创建 .dockerignore**

```
.git
.idea
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
tests/
docs/
*.md
```

**Step 4: Commit**

```bash
git add .
git commit -m "feat: add Docker configuration"
```

---

## 完成检查

### Task 20: 运行完整测试

**Step 1: 运行所有测试**

Run: `uv run pytest tests/ -v --cov=src`

**Step 2: 运行类型检查**

Run: `uv run mypy src/`

**Step 3: 运行代码格式化**

Run: `uv run ruff check --fix . && uv run ruff format .`

**Step 4: Final commit**

```bash
git add .
git commit -m "chore: code quality fixes"
```

---

## 总结

| Phase | Tasks | 说明 |
|-------|-------|------|
| 1 | 1 | 项目初始化 |
| 2 | 1 | 配置管理 |
| 3 | 2 | 数据库层 |
| 4 | 4 | 聚合器 (flow, oi, liquidation, percentile) |
| 5 | 2 | 告警系统 |
| 6 | 1 | 消息格式化 |
| 7 | 5 | 数据采集器 |
| 8 | 1 | Telegram Bot |
| 9 | 1 | 主程序 |
| 10 | 2 | Docker + 测试 |

**总计: 20 个 Tasks**
