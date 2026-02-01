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
