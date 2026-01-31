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
