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
