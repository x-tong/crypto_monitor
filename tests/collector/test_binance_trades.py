# tests/collector/test_binance_trades.py
from unittest.mock import AsyncMock

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
