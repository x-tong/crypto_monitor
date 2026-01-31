import json
import pytest
from unittest.mock import AsyncMock

from src.client.binance import BinanceClient


@pytest.mark.asyncio
async def test_process_ws_message():
    client = BinanceClient()

    message = json.dumps({
        "e": "aggTrade",
        "s": "BTCUSDT",
        "p": "42000.0",
        "q": "1.5",
        "T": 1704067200000,
        "m": False,  # buyer is maker = False means taker buy
    })

    received = []

    async def callback(trade_data):
        received.append(trade_data)

    await client._process_ws_message(message, callback)

    assert len(received) == 1
    assert received[0]["symbol"] == "BTCUSDT"
    assert received[0]["price"] == 42000.0
    assert received[0]["side"] == "buy"


@pytest.mark.asyncio
async def test_process_ws_message_sell():
    client = BinanceClient()

    message = json.dumps({
        "e": "aggTrade",
        "s": "BTCUSDT",
        "p": "42000.0",
        "q": "1.5",
        "T": 1704067200000,
        "m": True,  # buyer is maker = True means taker sell
    })

    received = []

    async def callback(trade_data):
        received.append(trade_data)

    await client._process_ws_message(message, callback)

    assert len(received) == 1
    assert received[0]["side"] == "sell"


@pytest.mark.asyncio
async def test_process_force_order_message():
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
