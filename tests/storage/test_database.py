# tests/storage/test_database.py
import time

import pytest

from src.storage.database import Database
from src.storage.models import Liquidation, OISnapshot, PriceAlert, Trade


@pytest.fixture
async def db(tmp_path):
    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    await database.init()
    yield database
    await database.close()


async def test_insert_and_get_trades(db: Database):
    now = int(time.time() * 1000)
    trade = Trade(
        id=None,
        exchange="binance",
        symbol="BTC/USDT:USDT",
        timestamp=now,
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


async def test_insert_and_get_liquidations(db: Database):
    now = int(time.time() * 1000)
    liq = Liquidation(
        id=None,
        exchange="binance",
        symbol="BTC/USDT:USDT",
        timestamp=now,
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
    now = int(time.time() * 1000)
    oi = OISnapshot(
        id=None,
        exchange="binance",
        symbol="BTC/USDT:USDT",
        timestamp=now,
        open_interest=50000.0,
        open_interest_usd=5000000000.0,
    )
    await db.insert_oi_snapshot(oi)

    latest = await db.get_latest_oi("BTC/USDT:USDT")
    assert latest is not None
    assert latest.open_interest_usd == 5000000000.0


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

    now = int(time.time() * 1000)

    # 插入两条记录：现在和30分钟前
    for i, offset in enumerate([0, 30 * 60 * 1000]):
        indicator = MarketIndicator(
            id=None,
            symbol="BTC/USDT:USDT",
            timestamp=now - offset,
            top_account_ratio=1.5 + i * 0.1,
            top_position_ratio=1.6,
            global_account_ratio=0.9,
            taker_buy_sell_ratio=1.1,
        )
        await db.insert_market_indicator(indicator)

    history = await db.get_market_indicator_history("BTC/USDT:USDT", hours=2)
    assert len(history) == 2

    await db.close()


async def test_insert_and_get_long_short_snapshot(db: Database):
    now = int(time.time() * 1000)
    await db.insert_long_short_snapshot(
        symbol="BTCUSDT",
        timestamp=now,
        ratio_type="global",
        long_ratio=0.55,
        short_ratio=0.45,
        long_short_ratio=1.22,
    )

    snapshots = await db.get_long_short_snapshots("BTCUSDT", "global", hours=1)
    assert len(snapshots) == 1
    assert snapshots[0]["long_ratio"] == 0.55
    assert snapshots[0]["ratio_type"] == "global"


async def test_get_latest_long_short_snapshot(db: Database):
    now = int(time.time() * 1000)
    await db.insert_long_short_snapshot(
        symbol="BTCUSDT",
        timestamp=now - 3600000,
        ratio_type="top_position",
        long_ratio=0.60,
        short_ratio=0.40,
        long_short_ratio=1.50,
    )
    await db.insert_long_short_snapshot(
        symbol="BTCUSDT",
        timestamp=now,
        ratio_type="top_position",
        long_ratio=0.65,
        short_ratio=0.35,
        long_short_ratio=1.86,
    )

    latest = await db.get_latest_long_short_snapshot("BTCUSDT", "top_position")
    assert latest is not None
    assert latest["long_ratio"] == 0.65


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
