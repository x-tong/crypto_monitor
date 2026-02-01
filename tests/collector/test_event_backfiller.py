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
    await db.insert_extreme_event(event)

    # 从数据库获取带 id 的事件
    events = await db.get_extreme_events("BTC", "flow_1h", 30)
    event_with_id = events[0]

    # Mock get_klines 返回价格
    mock_kline = MagicMock()
    mock_kline.close = 82500.0
    mock_client.get_klines = AsyncMock(return_value=[mock_kline])

    backfiller = EventBackfiller(db, mock_client)
    await backfiller.backfill_one(event_with_id, now)

    # 验证价格已更新
    events = await db.get_extreme_events("BTC", "flow_1h", 30)
    assert events[0].price_4h == 82500.0
