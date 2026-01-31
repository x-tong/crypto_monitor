# tests/collector/test_binance_trades.py

import pytest

from src.collector.binance_trades import BinanceTradesCollector
from src.storage.models import Trade


@pytest.mark.asyncio
async def test_handle_trade_filters_small_trades():
    received: list[Trade] = []

    async def on_trade(trade: Trade) -> None:
        received.append(trade)

    collector = BinanceTradesCollector(
        symbol="BTC/USDT:USDT",
        threshold_usd=100000,
        on_trade=on_trade,
    )

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

    await collector._handle_trade(small_trade)
    await collector._handle_trade(large_trade)

    assert len(received) == 1
    assert received[0].value_usd == 126000.0
    assert received[0].side == "buy"


@pytest.mark.asyncio
async def test_handle_trade_sets_correct_fields():
    received: list[Trade] = []

    async def on_trade(trade: Trade) -> None:
        received.append(trade)

    collector = BinanceTradesCollector(
        symbol="BTC/USDT:USDT",
        threshold_usd=100000,
        on_trade=on_trade,
    )

    trade_data = {
        "symbol": "BTCUSDT",
        "price": 100000.0,
        "quantity": 1.5,
        "timestamp": 1704067200000,
        "side": "sell",
    }

    await collector._handle_trade(trade_data)

    assert len(received) == 1
    assert received[0].exchange == "binance"
    assert received[0].symbol == "BTC/USDT:USDT"
    assert received[0].price == 100000.0
    assert received[0].amount == 1.5
    assert received[0].side == "sell"
    assert received[0].value_usd == 150000.0
