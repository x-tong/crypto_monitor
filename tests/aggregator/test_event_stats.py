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
