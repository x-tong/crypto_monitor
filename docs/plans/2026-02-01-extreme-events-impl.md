# 极端事件历史参考功能 - 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 当 P90+ 极端值出现时，显示历史统计和最近案例，帮助用户判断是顶/底还是中继。

**Architecture:** 新增 `extreme_events` 表存储极端事件，实时检测 P90+ 并记录，定时回填后续价格，报告中附加历史统计。三窗口（7d/30d/90d）独立计算百分位和触发。

**Tech Stack:** Python 3.14, aiosqlite, aiohttp (Binance API)

---

## Task 1: ExtremeEvent 数据模型

**Files:**
- Modify: `src/storage/models.py`
- Test: `tests/storage/test_models.py`

**Step 1: Write the failing test**

在 `tests/storage/test_models.py` 末尾添加：

```python
def test_extreme_event_model():
    from src.storage.models import ExtremeEvent

    event = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=1706600000000,
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    assert event.symbol == "BTC"
    assert event.window_days == 30
    assert event.price_4h is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/storage/test_models.py::test_extreme_event_model -v`
Expected: FAIL with "cannot import name 'ExtremeEvent'"

**Step 3: Write minimal implementation**

在 `src/storage/models.py` 末尾添加：

```python
@dataclass
class ExtremeEvent:
    id: int | None
    symbol: str                    # BTC / ETH
    dimension: str                 # flow_1h / oi_change_1h / funding_rate / ...
    window_days: int               # 7 / 30 / 90
    triggered_at: int              # 触发时间 (ms)
    value: float                   # 触发时的值
    percentile: float              # 百分位
    price_at_trigger: float        # 触发时价格
    price_4h: float | None         # 4h 后价格
    price_12h: float | None        # 12h 后价格
    price_24h: float | None        # 24h 后价格
    price_48h: float | None        # 48h 后价格
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/storage/test_models.py::test_extreme_event_model -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/storage/models.py tests/storage/test_models.py
git commit -m "feat: 添加 ExtremeEvent 数据模型"
```

---

## Task 2: extreme_events 表 CRUD

**Files:**
- Modify: `src/storage/database.py`
- Test: `tests/storage/test_database.py`

**Step 1: Write the failing tests**

在 `tests/storage/test_database.py` 末尾添加：

```python
async def test_extreme_events_table_created(db: Database):
    """验证表创建"""
    assert db.conn is not None
    cursor = await db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='extreme_events'"
    )
    row = await cursor.fetchone()
    assert row is not None


async def test_insert_and_get_extreme_event(db: Database):
    from src.storage.models import ExtremeEvent

    event = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=1706600000000,
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    event_id = await db.insert_extreme_event(event)
    assert event_id > 0

    events = await db.get_extreme_events("BTC", "flow_1h", 30, limit=10)
    assert len(events) == 1
    assert events[0].percentile == 92.5


async def test_get_extreme_events_completed_only(db: Database):
    """只返回有完整后续价格的事件"""
    from src.storage.models import ExtremeEvent

    # 插入一个完整的事件
    complete = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=1706500000000,
        value=50_000_000.0,
        percentile=95.0,
        price_at_trigger=80000.0,
        price_4h=80500.0,
        price_12h=79000.0,
        price_24h=78000.0,
        price_48h=79500.0,
    )
    await db.insert_extreme_event(complete)

    # 插入一个不完整的事件
    incomplete = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=1706600000000,
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    await db.insert_extreme_event(incomplete)

    # 获取完整事件
    events = await db.get_extreme_events("BTC", "flow_1h", 30, completed_only=True)
    assert len(events) == 1
    assert events[0].price_48h == 79500.0


async def test_update_extreme_event_prices(db: Database):
    """测试回填后续价格"""
    from src.storage.models import ExtremeEvent

    event = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=1706600000000,
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    event_id = await db.insert_extreme_event(event)

    await db.update_extreme_event_price(event_id, "price_4h", 82500.0)

    events = await db.get_extreme_events("BTC", "flow_1h", 30)
    assert events[0].price_4h == 82500.0


async def test_get_pending_backfill_events(db: Database):
    """测试获取待回填事件"""
    import time

    from src.storage.models import ExtremeEvent

    now = int(time.time() * 1000)

    # 插入一个 5 小时前的事件（应该回填 price_4h）
    old_event = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=now - 5 * 3600 * 1000,
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    await db.insert_extreme_event(old_event)

    pending = await db.get_pending_backfill_events()
    assert len(pending) >= 1
    assert any(e.price_4h is None for e in pending)


async def test_check_cooldown(db: Database):
    """测试冷却期检查"""
    import time

    from src.storage.models import ExtremeEvent

    now = int(time.time() * 1000)

    event = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=now - 30 * 60 * 1000,  # 30 分钟前
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    await db.insert_extreme_event(event)

    # 冷却期内
    in_cooldown = await db.is_in_cooldown("BTC", "flow_1h", 30, cooldown_hours=1)
    assert in_cooldown is True

    # 不同窗口不受影响
    not_in_cooldown = await db.is_in_cooldown("BTC", "flow_1h", 7, cooldown_hours=1)
    assert not_in_cooldown is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/storage/test_database.py::test_extreme_events_table_created -v`
Expected: FAIL with "no such table: extreme_events"

**Step 3: Write implementation**

在 `src/storage/database.py` 的 `_create_tables` 方法中添加表定义，在类中添加 CRUD 方法：

```python
# 在 _create_tables 的 executescript 中添加：
            CREATE TABLE IF NOT EXISTS extreme_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                dimension TEXT NOT NULL,
                window_days INTEGER NOT NULL,
                triggered_at INTEGER NOT NULL,
                value REAL NOT NULL,
                percentile REAL NOT NULL,
                price_at_trigger REAL NOT NULL,
                price_4h REAL,
                price_12h REAL,
                price_24h REAL,
                price_48h REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_extreme_events_lookup
                ON extreme_events(symbol, dimension, window_days, triggered_at);
```

在 `Database` 类末尾添加方法：

```python
    async def insert_extreme_event(self, event: "ExtremeEvent") -> int:
        from .models import ExtremeEvent  # noqa: F811

        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO extreme_events
               (symbol, dimension, window_days, triggered_at, value, percentile,
                price_at_trigger, price_4h, price_12h, price_24h, price_48h)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.symbol,
                event.dimension,
                event.window_days,
                event.triggered_at,
                event.value,
                event.percentile,
                event.price_at_trigger,
                event.price_4h,
                event.price_12h,
                event.price_24h,
                event.price_48h,
            ),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_extreme_events(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
        limit: int = 20,
        completed_only: bool = False,
    ) -> list["ExtremeEvent"]:
        from .models import ExtremeEvent

        assert self.conn is not None
        query = """SELECT id, symbol, dimension, window_days, triggered_at, value,
                          percentile, price_at_trigger, price_4h, price_12h, price_24h, price_48h
                   FROM extreme_events
                   WHERE symbol = ? AND dimension = ? AND window_days = ?"""
        if completed_only:
            query += " AND price_48h IS NOT NULL"
        query += " ORDER BY triggered_at DESC LIMIT ?"
        cursor = await self.conn.execute(query, (symbol, dimension, window_days, limit))
        rows = await cursor.fetchall()
        return [ExtremeEvent(*row) for row in rows]

    async def update_extreme_event_price(
        self, event_id: int, price_field: str, price: float
    ) -> None:
        assert self.conn is not None
        valid_fields = {"price_4h", "price_12h", "price_24h", "price_48h"}
        if price_field not in valid_fields:
            raise ValueError(f"Invalid price field: {price_field}")
        await self.conn.execute(
            f"UPDATE extreme_events SET {price_field} = ? WHERE id = ?",
            (price, event_id),
        )
        await self.conn.commit()

    async def get_pending_backfill_events(self) -> list["ExtremeEvent"]:
        """获取需要回填后续价格的事件"""
        from .models import ExtremeEvent

        assert self.conn is not None
        now = int(time.time() * 1000)
        cursor = await self.conn.execute(
            """SELECT id, symbol, dimension, window_days, triggered_at, value,
                      percentile, price_at_trigger, price_4h, price_12h, price_24h, price_48h
               FROM extreme_events
               WHERE (price_4h IS NULL AND triggered_at <= ?)
                  OR (price_12h IS NULL AND triggered_at <= ?)
                  OR (price_24h IS NULL AND triggered_at <= ?)
                  OR (price_48h IS NULL AND triggered_at <= ?)
               ORDER BY triggered_at ASC""",
            (
                now - 4 * 3600 * 1000,
                now - 12 * 3600 * 1000,
                now - 24 * 3600 * 1000,
                now - 48 * 3600 * 1000,
            ),
        )
        rows = await cursor.fetchall()
        return [ExtremeEvent(*row) for row in rows]

    async def is_in_cooldown(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
        cooldown_hours: int = 1,
    ) -> bool:
        """检查是否在冷却期内"""
        assert self.conn is not None
        cutoff = int(time.time() * 1000) - cooldown_hours * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT 1 FROM extreme_events
               WHERE symbol = ? AND dimension = ? AND window_days = ? AND triggered_at > ?
               LIMIT 1""",
            (symbol, dimension, window_days, cutoff),
        )
        row = await cursor.fetchone()
        return row is not None
```

**Step 4: Run all tests to verify they pass**

Run: `uv run pytest tests/storage/test_database.py -v -k extreme`
Expected: All 6 extreme_events tests PASS

**Step 5: Commit**

```bash
git add src/storage/database.py tests/storage/test_database.py
git commit -m "feat: 添加 extreme_events 表和 CRUD 操作"
```

---

## Task 3: 多窗口百分位计算

**Files:**
- Modify: `src/aggregator/percentile.py`
- Test: `tests/aggregator/test_percentile.py`

**Step 1: Write the failing tests**

在 `tests/aggregator/test_percentile.py` 末尾添加：

```python
def test_calculate_percentile_multi_window():
    from src.aggregator.percentile import calculate_percentile_multi_window

    # 模拟 30 天数据，每天一个值
    history = list(range(10, 310, 10))  # 10, 20, ..., 300

    result = calculate_percentile_multi_window(
        value=250.0,
        history=history,
        windows=[7, 30],
    )
    assert "7d" in result
    assert "30d" in result
    # 7d: 最后 7 个值是 240, 250, 260, 270, 280, 290, 300
    # 250 比 240 大，所以 percentile = 1/7 * 100 = 14.3
    assert result["7d"] == pytest.approx(14.3, abs=0.1)
    # 30d: 最后 30 个值是 10, 20, ..., 300
    # 250 比 240 个值大（10-240），所以 percentile = 24/30 * 100 = 80
    assert result["30d"] == pytest.approx(80.0, abs=0.1)


def test_calculate_percentile_multi_window_short_history():
    from src.aggregator.percentile import calculate_percentile_multi_window

    # 只有 10 天数据
    history = list(range(10, 110, 10))  # 10, 20, ..., 100

    result = calculate_percentile_multi_window(
        value=75.0,
        history=history,
        windows=[7, 30, 90],
    )
    # 7d 正常计算
    assert "7d" in result
    # 30d 和 90d 数据不足，返回 None
    assert result.get("30d") is None
    assert result.get("90d") is None


def test_format_multi_window_percentile():
    from src.aggregator.percentile import format_multi_window_percentile

    percentiles = {"7d": 92.5, "30d": 85.0, "90d": 70.0}
    result = format_multi_window_percentile(percentiles)
    assert "P93(7d)" in result or "P92(7d)" in result  # 四舍五入
    assert "P85(30d)" in result
    assert "P70(90d)" in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/aggregator/test_percentile.py::test_calculate_percentile_multi_window -v`
Expected: FAIL with "cannot import name 'calculate_percentile_multi_window'"

**Step 3: Write implementation**

在 `src/aggregator/percentile.py` 末尾添加：

```python
def calculate_percentile_multi_window(
    value: float,
    history: list[float],
    windows: list[int] = [7, 30, 90],
) -> dict[str, float | None]:
    """
    计算多窗口百分位

    Args:
        value: 当前值
        history: 历史数据列表（按时间顺序，每天一个值）
        windows: 窗口大小列表（天）

    Returns:
        {窗口名: 百分位} 字典，数据不足时为 None
    """
    result: dict[str, float | None] = {}
    for window in windows:
        key = f"{window}d"
        if len(history) < window:
            result[key] = None
        else:
            window_data = history[-window:]
            result[key] = calculate_percentile(value, window_data)
    return result


def format_multi_window_percentile(percentiles: dict[str, float | None]) -> str:
    """格式化多窗口百分位显示"""
    parts = []
    for key in ["7d", "30d", "90d"]:
        pct = percentiles.get(key)
        if pct is not None:
            parts.append(f"P{int(round(pct))}({key})")
    return " / ".join(parts)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/aggregator/test_percentile.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/aggregator/percentile.py tests/aggregator/test_percentile.py
git commit -m "feat: 添加多窗口百分位计算"
```

---

## Task 4: 极端事件检测与记录

**Files:**
- Create: `src/aggregator/extreme_tracker.py`
- Create: `tests/aggregator/test_extreme_tracker.py`

**Step 1: Write the failing tests**

创建 `tests/aggregator/test_extreme_tracker.py`：

```python
# tests/aggregator/test_extreme_tracker.py
import pytest

from src.aggregator.extreme_tracker import ExtremeTracker


@pytest.fixture
async def db(tmp_path):
    from src.storage.database import Database

    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    await database.init()
    yield database
    await database.close()


async def test_detect_extreme_single_window(db):
    tracker = ExtremeTracker(db)

    # 模拟 7 天历史数据
    history = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
    current_value = 95.0  # 超过所有历史值

    extremes = tracker.detect_extremes(
        value=current_value,
        history=history,
        threshold=90,
    )

    assert "7d" in extremes
    assert extremes["7d"] == 100.0  # 超过所有值


async def test_record_extreme_event(db):
    import time

    tracker = ExtremeTracker(db)

    await tracker.record_event(
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        value=47_700_000.0,
        percentile=92.5,
        price=82000.0,
    )

    events = await db.get_extreme_events("BTC", "flow_1h", 30)
    assert len(events) == 1
    assert events[0].value == 47_700_000.0


async def test_record_respects_cooldown(db):
    import time

    tracker = ExtremeTracker(db)

    # 第一次记录
    await tracker.record_event(
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        value=47_700_000.0,
        percentile=92.5,
        price=82000.0,
    )

    # 立即再次记录（应被冷却期阻止）
    await tracker.record_event(
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        value=50_000_000.0,
        percentile=95.0,
        price=82500.0,
    )

    events = await db.get_extreme_events("BTC", "flow_1h", 30)
    assert len(events) == 1  # 只有一条记录


async def test_different_windows_independent_cooldown(db):
    tracker = ExtremeTracker(db)

    # 30d 窗口记录
    await tracker.record_event(
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        value=47_700_000.0,
        percentile=92.5,
        price=82000.0,
    )

    # 7d 窗口记录（不受 30d 冷却影响）
    await tracker.record_event(
        symbol="BTC",
        dimension="flow_1h",
        window_days=7,
        value=47_700_000.0,
        percentile=95.0,
        price=82000.0,
    )

    events_30d = await db.get_extreme_events("BTC", "flow_1h", 30)
    events_7d = await db.get_extreme_events("BTC", "flow_1h", 7)
    assert len(events_30d) == 1
    assert len(events_7d) == 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/aggregator/test_extreme_tracker.py -v`
Expected: FAIL with "No module named 'src.aggregator.extreme_tracker'"

**Step 3: Write implementation**

创建 `src/aggregator/extreme_tracker.py`：

```python
# src/aggregator/extreme_tracker.py
import time

from src.aggregator.percentile import calculate_percentile_multi_window
from src.storage.database import Database
from src.storage.models import ExtremeEvent


class ExtremeTracker:
    """极端事件检测与记录"""

    def __init__(self, db: Database, cooldown_hours: int = 1):
        self.db = db
        self.cooldown_hours = cooldown_hours

    def detect_extremes(
        self,
        value: float,
        history: list[float],
        threshold: float = 90,
        windows: list[int] = [7, 30, 90],
    ) -> dict[str, float]:
        """
        检测哪些窗口达到极端值

        Returns:
            {窗口名: 百分位} 只包含 >= threshold 的窗口
        """
        percentiles = calculate_percentile_multi_window(value, history, windows)
        return {
            k: v
            for k, v in percentiles.items()
            if v is not None and v >= threshold
        }

    async def record_event(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
        value: float,
        percentile: float,
        price: float,
    ) -> int | None:
        """
        记录极端事件

        Returns:
            事件 ID，如果在冷却期内则返回 None
        """
        # 检查冷却期
        in_cooldown = await self.db.is_in_cooldown(
            symbol, dimension, window_days, self.cooldown_hours
        )
        if in_cooldown:
            return None

        event = ExtremeEvent(
            id=None,
            symbol=symbol,
            dimension=dimension,
            window_days=window_days,
            triggered_at=int(time.time() * 1000),
            value=value,
            percentile=percentile,
            price_at_trigger=price,
            price_4h=None,
            price_12h=None,
            price_24h=None,
            price_48h=None,
        )
        return await self.db.insert_extreme_event(event)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/aggregator/test_extreme_tracker.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/aggregator/extreme_tracker.py tests/aggregator/test_extreme_tracker.py
git commit -m "feat: 添加极端事件检测与记录"
```

---

## Task 5: 历史统计查询

**Files:**
- Create: `src/aggregator/event_stats.py`
- Create: `tests/aggregator/test_event_stats.py`

**Step 1: Write the failing tests**

创建 `tests/aggregator/test_event_stats.py`：

```python
# tests/aggregator/test_event_stats.py
import pytest

from src.aggregator.event_stats import EventStats


@pytest.fixture
async def db_with_events(tmp_path):
    from src.storage.database import Database
    from src.storage.models import ExtremeEvent

    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    await database.init()

    # 插入 10 个完整的历史事件
    base_time = 1706000000000
    for i in range(10):
        event = ExtremeEvent(
            id=None,
            symbol="BTC",
            dimension="flow_1h",
            window_days=30,
            triggered_at=base_time + i * 3600 * 1000 * 24,  # 每天一个
            value=40_000_000.0 + i * 1_000_000,
            percentile=90.0 + i * 0.5,
            price_at_trigger=80000.0 + i * 100,
            price_4h=80000.0 + i * 100 + 50,  # 略涨
            price_12h=80000.0 + i * 100 - 100,  # 略跌
            price_24h=80000.0 + i * 100 - 500 if i % 2 == 0 else 80000.0 + i * 100 + 300,
            price_48h=80000.0 + i * 100 - 200,
        )
        await database.insert_extreme_event(event)

    yield database
    await database.close()


async def test_get_stats_summary(db_with_events):
    stats = EventStats(db_with_events)

    summary = await stats.get_summary("BTC", "flow_1h", 30, limit=10)

    assert summary["count"] == 10
    assert "24h" in summary["stats"]
    assert "up_pct" in summary["stats"]["24h"]
    assert "down_pct" in summary["stats"]["24h"]
    assert "avg_change" in summary["stats"]["24h"]


async def test_get_stats_up_down_ratio(db_with_events):
    stats = EventStats(db_with_events)

    summary = await stats.get_summary("BTC", "flow_1h", 30)

    # 10 个事件中，5 个 24h 后涨（奇数索引），5 个跌（偶数索引）
    assert summary["stats"]["24h"]["up_pct"] == 50.0
    assert summary["stats"]["24h"]["down_pct"] == 50.0


async def test_get_latest_event(db_with_events):
    stats = EventStats(db_with_events)

    latest = await stats.get_latest_event("BTC", "flow_1h", 30)

    assert latest is not None
    assert latest["triggered_at"] is not None
    assert latest["price_at_trigger"] is not None
    assert latest["change_24h"] is not None


async def test_stats_insufficient_data(tmp_path):
    from src.storage.database import Database

    db = Database(str(tmp_path / "test.db"))
    await db.init()

    stats = EventStats(db)
    summary = await stats.get_summary("BTC", "flow_1h", 30)

    assert summary["count"] == 0
    assert summary["stats"] == {}

    await db.close()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/aggregator/test_event_stats.py -v`
Expected: FAIL with "No module named 'src.aggregator.event_stats'"

**Step 3: Write implementation**

创建 `src/aggregator/event_stats.py`：

```python
# src/aggregator/event_stats.py
from typing import Any

from src.storage.database import Database


class EventStats:
    """极端事件历史统计"""

    def __init__(self, db: Database):
        self.db = db

    async def get_summary(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        获取历史事件统计摘要

        Returns:
            {
                "count": 事件数量,
                "stats": {
                    "4h": {"up_pct": 涨占比, "down_pct": 跌占比, "avg_change": 平均涨跌幅},
                    "12h": {...},
                    "24h": {...},
                    "48h": {...},
                },
            }
        """
        events = await self.db.get_extreme_events(
            symbol, dimension, window_days, limit=limit, completed_only=True
        )

        if not events:
            return {"count": 0, "stats": {}}

        stats: dict[str, dict[str, float]] = {}
        for period, field in [
            ("4h", "price_4h"),
            ("12h", "price_12h"),
            ("24h", "price_24h"),
            ("48h", "price_48h"),
        ]:
            changes = []
            for e in events:
                price_after = getattr(e, field)
                if price_after is not None and e.price_at_trigger > 0:
                    change = (price_after - e.price_at_trigger) / e.price_at_trigger * 100
                    changes.append(change)

            if changes:
                up_count = sum(1 for c in changes if c > 0)
                down_count = sum(1 for c in changes if c < 0)
                total = len(changes)
                stats[period] = {
                    "up_pct": round(up_count / total * 100, 1),
                    "down_pct": round(down_count / total * 100, 1),
                    "avg_change": round(sum(changes) / total, 2),
                }

        return {"count": len(events), "stats": stats}

    async def get_latest_event(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
    ) -> dict[str, Any] | None:
        """获取最近一次完整事件"""
        events = await self.db.get_extreme_events(
            symbol, dimension, window_days, limit=1, completed_only=True
        )
        if not events:
            return None

        e = events[0]
        change_24h = None
        if e.price_24h is not None and e.price_at_trigger > 0:
            change_24h = round(
                (e.price_24h - e.price_at_trigger) / e.price_at_trigger * 100, 2
            )

        return {
            "triggered_at": e.triggered_at,
            "price_at_trigger": e.price_at_trigger,
            "price_24h": e.price_24h,
            "change_24h": change_24h,
        }
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/aggregator/test_event_stats.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/aggregator/event_stats.py tests/aggregator/test_event_stats.py
git commit -m "feat: 添加极端事件历史统计查询"
```

---

## Task 6: 格式化历史参考区块

**Files:**
- Modify: `src/notifier/formatter.py`
- Test: `tests/notifier/test_formatter.py`

**Step 1: Write the failing tests**

在 `tests/notifier/test_formatter.py` 末尾添加：

```python
def test_format_history_reference_block():
    from src.notifier.formatter import format_history_reference_block

    stats = {
        "7d": {
            "count": 20,
            "stats": {
                "24h": {"up_pct": 45.0, "down_pct": 55.0, "avg_change": -1.2},
            },
        },
        "30d": {
            "count": 15,
            "stats": {
                "24h": {"up_pct": 35.0, "down_pct": 65.0, "avg_change": -2.8},
            },
        },
    }
    latest = {
        "30d": {
            "triggered_at": 1706400000000,  # 2024-01-28
            "price_at_trigger": 82000.0,
            "change_24h": -4.8,
        }
    }

    result = format_history_reference_block(stats, latest)

    assert "7d P90+" in result
    assert "近20次" in result
    assert "↑45%" in result
    assert "↓55%" in result
    assert "30d P90+" in result
    assert "最近(30d)" in result
    assert "-4.8%" in result


def test_format_history_reference_block_insufficient_data():
    from src.notifier.formatter import format_history_reference_block

    stats = {"7d": {"count": 3, "stats": {}}}  # 少于 5 次
    latest = {}

    result = format_history_reference_block(stats, latest)

    assert "数据积累中" in result


def test_format_history_reference_block_empty():
    from src.notifier.formatter import format_history_reference_block

    result = format_history_reference_block({}, {})
    assert result == ""
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/notifier/test_formatter.py::test_format_history_reference_block -v`
Expected: FAIL with "cannot import name 'format_history_reference_block'"

**Step 3: Write implementation**

在 `src/notifier/formatter.py` 末尾添加：

```python
def _format_timestamp_short(ts_ms: int) -> str:
    """格式化时间戳为短格式 (M/D)"""
    from datetime import UTC, datetime

    dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    return dt.strftime("%-m/%-d")


def format_history_reference_block(
    stats: dict[str, Any],
    latest: dict[str, Any],
    min_count: int = 5,
) -> str:
    """
    格式化历史参考区块

    Args:
        stats: {窗口: {count, stats}} 统计数据
        latest: {窗口: {triggered_at, price_at_trigger, change_24h}} 最近事件
        min_count: 最小样本数

    Returns:
        格式化的历史参考文本
    """
    if not stats:
        return ""

    lines = ["  ┌─ 📜 历史参考 ────────────────"]

    has_valid_data = False
    for window in ["7d", "30d", "90d"]:
        if window not in stats:
            continue

        window_stats = stats[window]
        count = window_stats.get("count", 0)

        if count < min_count:
            lines.append(f"  │ {window} P90+: 数据积累中 ({count}次)")
            continue

        has_valid_data = True
        period_stats = window_stats.get("stats", {})

        lines.append(f"  │ {window} P90+ (近{count}次):")

        # 显示 24h 统计
        if "24h" in period_stats:
            s = period_stats["24h"]
            up = s["up_pct"]
            down = s["down_pct"]
            avg = s["avg_change"]
            sign = "+" if avg >= 0 else ""
            lines.append(f"  │   24h: ↑{up:.0f}% / ↓{down:.0f}%  均值 {sign}{avg:.1f}%")

        lines.append("  │")

    # 显示最近案例（优先较长窗口）
    for window in ["90d", "30d", "7d"]:
        if window in latest and latest[window]:
            event = latest[window]
            date_str = _format_timestamp_short(event["triggered_at"])
            price = event["price_at_trigger"]
            change = event["change_24h"]
            if change is not None:
                sign = "+" if change >= 0 else ""
                lines.append(f"  │ 最近({window}): {date_str} ${price:,.0f} → 24h {sign}{change:.1f}%")
            break

    lines.append("  └───────────────────────────────")

    if not has_valid_data and not any("最近" in line for line in lines):
        return "  ┌─ 📜 历史参考 ────────────────\n  │ 数据积累中\n  └───────────────────────────────"

    return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/notifier/test_formatter.py -v -k history`
Expected: All history tests PASS

**Step 5: Commit**

```bash
git add src/notifier/formatter.py tests/notifier/test_formatter.py
git commit -m "feat: 添加历史参考区块格式化"
```

---

## Task 7: 价格回填任务

**Files:**
- Create: `src/collector/event_backfiller.py`
- Create: `tests/collector/test_event_backfiller.py`

**Step 1: Write the failing tests**

创建 `tests/collector/test_event_backfiller.py`：

```python
# tests/collector/test_event_backfiller.py
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.collector.event_backfiller import EventBackfiller


@pytest.fixture
async def db(tmp_path):
    from src.storage.database import Database

    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def mock_client():
    client = MagicMock()
    return client


async def test_backfill_determines_correct_fields(db, mock_client):
    from src.storage.models import ExtremeEvent

    now = int(time.time() * 1000)

    # 插入一个 5 小时前的事件
    event = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=now - 5 * 3600 * 1000,
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    await db.insert_extreme_event(event)

    backfiller = EventBackfiller(db, mock_client)
    fields = backfiller._get_pending_fields(event, now)

    assert "price_4h" in fields
    assert "price_12h" not in fields


async def test_backfill_updates_price(db, mock_client):
    from src.storage.models import ExtremeEvent

    now = int(time.time() * 1000)

    event = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=now - 5 * 3600 * 1000,
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    event_id = await db.insert_extreme_event(event)

    # Mock get_klines 返回价格
    mock_kline = MagicMock()
    mock_kline.close = 82500.0
    mock_client.get_klines = AsyncMock(return_value=[mock_kline])

    backfiller = EventBackfiller(db, mock_client)
    await backfiller.backfill_one(event, now)

    # 验证价格已更新
    events = await db.get_extreme_events("BTC", "flow_1h", 30)
    assert events[0].price_4h == 82500.0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/collector/test_event_backfiller.py -v`
Expected: FAIL with "No module named 'src.collector.event_backfiller'"

**Step 3: Write implementation**

创建 `src/collector/event_backfiller.py`：

```python
# src/collector/event_backfiller.py
import logging
import time
from typing import TYPE_CHECKING

from src.storage.database import Database
from src.storage.models import ExtremeEvent

if TYPE_CHECKING:
    from src.client.binance import BinanceClient

logger = logging.getLogger(__name__)

# 时间偏移量 (ms)
BACKFILL_OFFSETS = {
    "price_4h": 4 * 3600 * 1000,
    "price_12h": 12 * 3600 * 1000,
    "price_24h": 24 * 3600 * 1000,
    "price_48h": 48 * 3600 * 1000,
}


class EventBackfiller:
    """极端事件后续价格回填"""

    def __init__(self, db: Database, client: "BinanceClient"):
        self.db = db
        self.client = client

    def _get_pending_fields(
        self, event: ExtremeEvent, now_ms: int
    ) -> list[str]:
        """获取需要回填的字段"""
        pending = []
        for field, offset in BACKFILL_OFFSETS.items():
            current_value = getattr(event, field)
            if current_value is None and event.triggered_at + offset <= now_ms:
                pending.append(field)
        return pending

    async def _get_price_at(self, symbol: str, target_time_ms: int) -> float | None:
        """获取指定时间的价格"""
        try:
            # 将内部 symbol (BTC) 转换为 Binance symbol (BTCUSDT)
            binance_symbol = f"{symbol}USDT"
            klines = await self.client.get_klines(
                binance_symbol, "1h", limit=1
            )
            if klines:
                return klines[0].close
            return None
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
            return None

    async def backfill_one(self, event: ExtremeEvent, now_ms: int | None = None) -> int:
        """
        回填单个事件的后续价格

        Returns:
            回填的字段数量
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        pending_fields = self._get_pending_fields(event, now_ms)
        if not pending_fields:
            return 0

        filled_count = 0
        for field in pending_fields:
            offset = BACKFILL_OFFSETS[field]
            target_time = event.triggered_at + offset
            price = await self._get_price_at(event.symbol, target_time)

            if price is not None and event.id is not None:
                await self.db.update_extreme_event_price(event.id, field, price)
                filled_count += 1
                logger.info(
                    f"Backfilled {field} for event {event.id}: {price}"
                )

        return filled_count

    async def run(self) -> int:
        """
        运行回填任务

        Returns:
            回填的总字段数
        """
        events = await self.db.get_pending_backfill_events()
        total_filled = 0

        for event in events:
            filled = await self.backfill_one(event)
            total_filled += filled

        return total_filled
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/collector/test_event_backfiller.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/collector/event_backfiller.py tests/collector/test_event_backfiller.py
git commit -m "feat: 添加极端事件价格回填任务"
```

---

## Task 8: 历史回测脚本框架

**Files:**
- Create: `src/scripts/__init__.py`
- Create: `src/scripts/backfill_events.py`
- Create: `tests/scripts/__init__.py`
- Create: `tests/scripts/test_backfill_events.py`

**Step 1: Write the failing tests**

创建 `tests/scripts/__init__.py`（空文件）和 `tests/scripts/test_backfill_events.py`：

```python
# tests/scripts/test_backfill_events.py
import pytest


def test_parse_args():
    from src.scripts.backfill_events import parse_args

    args = parse_args(["--days", "365", "--symbol", "BTC"])
    assert args.days == 365
    assert args.symbol == "BTC"


def test_parse_args_defaults():
    from src.scripts.backfill_events import parse_args

    args = parse_args([])
    assert args.days == 365
    assert args.symbol is None  # 默认处理所有 symbol


async def test_calculate_historical_percentile():
    from src.scripts.backfill_events import calculate_historical_percentile

    # 模拟 30 天历史数据
    history = [float(i) for i in range(1, 31)]  # 1-30
    current_idx = 25  # 当前在第 26 天

    # 使用 7 天窗口
    result = calculate_historical_percentile(
        history, current_idx, value=28.0, window_days=7
    )

    # 窗口数据: 20-26，value=28 超过所有值
    assert result == 100.0


async def test_calculate_historical_percentile_insufficient_data():
    from src.scripts.backfill_events import calculate_historical_percentile

    history = [1.0, 2.0, 3.0]
    result = calculate_historical_percentile(
        history, current_idx=2, value=2.5, window_days=7
    )
    assert result is None  # 数据不足
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scripts/test_backfill_events.py -v`
Expected: FAIL with "No module named 'src.scripts'"

**Step 3: Write implementation**

创建 `src/scripts/__init__.py`（空文件）和 `src/scripts/backfill_events.py`：

```python
# src/scripts/backfill_events.py
"""
历史极端事件回测脚本

用法:
    uv run python -m src.scripts.backfill_events --days 365
    uv run python -m src.scripts.backfill_events --days 365 --symbol BTC
"""
import argparse
import asyncio
import logging
from typing import Sequence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="回测历史极端事件")
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="回测天数 (默认: 365)",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="只回测指定 symbol (默认: 全部)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要插入的事件，不实际写入",
    )
    return parser.parse_args(args)


def calculate_historical_percentile(
    history: list[float],
    current_idx: int,
    value: float,
    window_days: int,
) -> float | None:
    """
    计算历史某一时刻的滚动窗口百分位

    Args:
        history: 完整历史数据列表
        current_idx: 当前时刻在 history 中的索引
        value: 当前值
        window_days: 窗口大小（天）

    Returns:
        百分位，数据不足时返回 None
    """
    start_idx = max(0, current_idx - window_days + 1)
    window_data = history[start_idx:current_idx + 1]

    if len(window_data) < window_days:
        return None

    count_below = sum(1 for h in window_data if h < abs(value))
    return count_below / len(window_data) * 100


async def main() -> None:
    args = parse_args()
    logger.info(f"Starting backfill for {args.days} days")

    # TODO: 实现完整的回测逻辑
    # 1. 下载历史数据
    # 2. 计算每个时间点的百分位
    # 3. 识别 P90+ 事件
    # 4. 插入 extreme_events 表
    # 5. 回填后续价格

    logger.info("Backfill complete")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/scripts/test_backfill_events.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/scripts/__init__.py src/scripts/backfill_events.py tests/scripts/__init__.py tests/scripts/test_backfill_events.py
git commit -m "feat: 添加历史回测脚本框架"
```

---

## Task 9: 集成到报告生成

**Files:**
- Modify: `src/notifier/formatter.py` (format_insight_report)
- Test: `tests/notifier/test_formatter.py`

这个任务需要修改 `format_insight_report` 函数，在 P90+ 维度下方显示历史参考。由于这涉及到异步数据库查询，需要重构为接受预计算的历史数据。

**Step 1: Write the failing test**

在 `tests/notifier/test_formatter.py` 添加：

```python
def test_format_insight_report_with_history():
    from src.notifier.formatter import format_insight_report_with_history

    data = {
        "symbol": "BTC",
        "price": 82000.0,
        "price_change_1h": 0.5,
        "top_position_ratio": 1.8,
        "top_position_pct": 50.0,
        "top_position_pct_7d": 55.0,
        "top_position_pct_30d": 60.0,
        "top_position_pct_90d": 45.0,
        "top_position_change": 0.02,
        "global_account_ratio": 1.5,
        "global_account_pct": 78.0,
        "global_account_pct_7d": 80.0,
        "global_account_pct_30d": 75.0,
        "global_account_pct_90d": 70.0,
        "global_account_change": 0.01,
        "flow_1h": 47_700_000.0,
        "flow_1h_pct": 92.0,  # P90+ 触发
        "flow_1h_pct_7d": 95.0,
        "flow_1h_pct_30d": 92.0,
        "flow_1h_pct_90d": 70.0,
        "flow_binance": 47_700_000.0,
        "taker_ratio": 0.8,
        "taker_ratio_pct": 50.0,
        "taker_ratio_pct_7d": 50.0,
        "taker_ratio_pct_30d": 50.0,
        "taker_ratio_pct_90d": 50.0,
        "oi_value": 7_400_000_000.0,
        "oi_change_1h": 0.5,
        "oi_change_1h_pct": 60.0,
        "oi_change_1h_pct_7d": 60.0,
        "oi_change_1h_pct_30d": 55.0,
        "oi_change_1h_pct_90d": 50.0,
        "liq_1h_total": 500_000.0,
        "liq_long_ratio": 0.7,
        "funding_rate": 0.01,
        "funding_rate_pct": 50.0,
        "funding_rate_pct_7d": 50.0,
        "funding_rate_pct_30d": 50.0,
        "funding_rate_pct_90d": 50.0,
        "spot_perp_spread": 0.01,
        "spot_perp_spread_pct": 50.0,
        "spot_perp_spread_pct_7d": 50.0,
        "spot_perp_spread_pct_30d": 50.0,
        "spot_perp_spread_pct_90d": 50.0,
    }

    history_data = {
        "flow_1h": {
            "stats": {
                "7d": {"count": 20, "stats": {"24h": {"up_pct": 45.0, "down_pct": 55.0, "avg_change": -1.2}}},
                "30d": {"count": 15, "stats": {"24h": {"up_pct": 35.0, "down_pct": 65.0, "avg_change": -2.8}}},
            },
            "latest": {
                "30d": {"triggered_at": 1706400000000, "price_at_trigger": 82000.0, "change_24h": -4.8}
            },
        }
    }

    result = format_insight_report_with_history(data, history_data)

    assert "P95(7d) / P92(30d) / P70(90d)" in result
    assert "历史参考" in result
    assert "7d P90+" in result
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/notifier/test_formatter.py::test_format_insight_report_with_history -v`
Expected: FAIL with "cannot import name 'format_insight_report_with_history'"

**Step 3: Write implementation**

在 `src/notifier/formatter.py` 添加新函数（保留原函数兼容）：

```python
def _format_multi_pct(pct_7d: float, pct_30d: float, pct_90d: float) -> str:
    """格式化三窗口百分位"""
    return f"P{int(pct_7d)}(7d) / P{int(pct_30d)}(30d) / P{int(pct_90d)}(90d)"


def _has_extreme(pct_7d: float, pct_30d: float, pct_90d: float, threshold: float = 90) -> bool:
    """检查是否有任一窗口达到极端值"""
    return pct_7d >= threshold or pct_30d >= threshold or pct_90d >= threshold


def format_insight_report_with_history(
    data: dict[str, Any],
    history_data: dict[str, Any] | None = None,
) -> str:
    """
    生成带历史参考的市场洞察报告

    Args:
        data: 市场数据（包含 _pct_7d/_pct_30d/_pct_90d 字段）
        history_data: {维度: {stats, latest}} 历史统计数据
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    history_data = history_data or {}

    # 转换比率为百分比
    top_long_pct = _ratio_to_pct(data["top_position_ratio"])
    top_short_pct = 100 - top_long_pct
    global_long_pct = _ratio_to_pct(data["global_account_ratio"])
    global_short_pct = 100 - global_long_pct
    taker_buy_pct = _ratio_to_pct(data["taker_ratio"])
    taker_sell_pct = 100 - taker_buy_pct

    # 变化方向和描述
    top_dir = "↑" if data["top_position_change"] > 0 else "↓"
    top_change_pct = abs(data["top_position_change"]) / max(data["top_position_ratio"], 0.01) * 100
    top_desc = _change_desc(data["top_position_change"])

    global_dir = "↑" if data["global_account_change"] > 0 else "↓"
    global_change_pct = (
        abs(data["global_account_change"]) / max(data["global_account_ratio"], 0.01) * 100
    )
    global_desc = _change_desc(data["global_account_change"])

    # 大户散户一致性判断
    both_long = top_long_pct > 50 and global_long_pct > 50
    both_short = top_long_pct < 50 and global_long_pct < 50
    if both_long:
        consensus = "大户散户一致看多"
    elif both_short:
        consensus = "大户散户一致看空"
    else:
        consensus = "大户散户存在分歧"

    # 资金流向
    flow_1h = _format_usd_signed(data["flow_1h"])
    flow_binance = _format_usd_signed(data["flow_binance"])
    flow_pct_str = _format_multi_pct(
        data.get("flow_1h_pct_7d", 50),
        data.get("flow_1h_pct_30d", 50),
        data.get("flow_1h_pct_90d", 50),
    )

    # Taker 描述
    if taker_buy_pct > 55:
        taker_desc = "买方主导"
    elif taker_buy_pct < 45:
        taker_desc = "卖方主导"
    else:
        taker_desc = "买卖均衡"

    # OI 解读
    oi_interp = _oi_interpretation(data["oi_change_1h"], data["price_change_1h"])

    # 爆仓
    liq_long_pct = int(data["liq_long_ratio"] * 100)
    liq_short_pct = 100 - liq_long_pct
    if data["liq_long_ratio"] > 0.65:
        liq_desc = "多头承压"
    elif data["liq_long_ratio"] < 0.35:
        liq_desc = "空头承压"
    else:
        liq_desc = "多空均衡"

    # 资金费率描述
    if data["funding_rate"] > 0.01:
        funding_desc = "多头付费，情绪偏多"
    elif data["funding_rate"] < -0.01:
        funding_desc = "空头付费，情绪偏空"
    else:
        funding_desc = "费率中性"

    # 构建资金流向部分（可能包含历史参考）
    flow_section = f"""💰 资金动向 [实时]

  主力净流向 (1h): {flow_1h}
    {flow_pct_str}
    Binance: {flow_binance}"""

    # 检查是否需要显示历史参考
    if _has_extreme(
        data.get("flow_1h_pct_7d", 0),
        data.get("flow_1h_pct_30d", 0),
        data.get("flow_1h_pct_90d", 0),
    ):
        flow_history = history_data.get("flow_1h", {})
        if flow_history:
            history_block = format_history_reference_block(
                flow_history.get("stats", {}),
                flow_history.get("latest", {}),
            )
            if history_block:
                flow_section += "\n\n" + history_block

    # 构建报告
    return f"""📊 {data["symbol"]} 市场洞察
━━━━━━━━━━━━━━━━━━━━
💵 ${data["price"]:,.0f} ({data["price_change_1h"]:+.1f}% vs 1h前)

━━━━━━━━━━━━━━━━━━━━
🎯 多空对比 [5m更新]

  大户: {top_long_pct}% 多 / {top_short_pct}% 空
        {top_dir}{top_change_pct:.0f}% vs 1h前 ({top_desc})

  散户: {global_long_pct}% 多 / {global_short_pct}% 空
        {global_dir}{global_change_pct:.0f}% vs 1h前 ({global_desc})

  → {consensus}

━━━━━━━━━━━━━━━━━━━━
{flow_section}

  Taker: {taker_buy_pct}% 买 / {taker_sell_pct}% 卖
         {taker_desc}

━━━━━━━━━━━━━━━━━━━━
📈 持仓 & 爆仓 [实时]

  OI: {_format_usd(data["oi_value"])}
      {data["oi_change_1h"]:+.1f}% vs 1h前
      → {oi_interp}

  爆仓 (1h): {_format_usd(data["liq_1h_total"])}
      多 {liq_long_pct}% / 空 {liq_short_pct}%
      → {liq_desc}

━━━━━━━━━━━━━━━━━━━━
📊 情绪指标

  资金费率: {data["funding_rate"]:+.3f}%
            {funding_desc}

  合约溢价: {data["spot_perp_spread"]:+.2f}%

⏰ {now}"""
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/notifier/test_formatter.py::test_format_insight_report_with_history -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/notifier/formatter.py tests/notifier/test_formatter.py
git commit -m "feat: 集成历史参考到市场洞察报告"
```

---

## Task 10: 运行全部测试并验证

**Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS

**Step 2: Run linting and type check**

```bash
uv run ruff check --fix . && uv run ruff format .
uv run mypy src/
```

Expected: No errors

**Step 3: Final commit**

```bash
git add .
git commit -m "chore: 代码格式化和类型检查通过"
```

---

## 后续任务（未包含在本计划中）

以下任务需要单独规划：

1. **完善回测脚本** — 实现完整的历史数据下载和百分位计算逻辑
2. **集成到主流程** — 在 `main.py` 中调用 `EventBackfiller` 定时任务
3. **修改现有报告生成** — 将 `format_insight_report` 调用改为 `format_insight_report_with_history`
4. **其他维度的历史参考** — 扩展到 OI、资金费率等维度
