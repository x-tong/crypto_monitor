# tests/aggregator/test_flow.py
from src.aggregator.flow import calculate_flow
from src.storage.models import Trade


def test_calculate_flow_net_positive():
    trades = [
        Trade(1, "binance", "BTC/USDT:USDT", 1706600000000, 100000, 1.0, "buy", 100000),
        Trade(2, "binance", "BTC/USDT:USDT", 1706600001000, 100000, 0.5, "sell", 50000),
        Trade(3, "binance", "BTC/USDT:USDT", 1706600002000, 100000, 0.8, "buy", 80000),
    ]

    result = calculate_flow(trades)

    assert result.net == 130000  # 180000 - 50000
    assert result.buy == 180000
    assert result.sell == 50000


def test_calculate_flow_by_exchange():
    trades = [
        Trade(1, "binance", "BTC/USDT:USDT", 1706600000000, 100000, 1.0, "buy", 100000),
        Trade(2, "binance", "BTC/USDT:USDT", 1706600001000, 100000, 0.5, "sell", 50000),
    ]

    result = calculate_flow(trades)

    assert result.by_exchange["binance"] == 50000  # 100000 - 50000


def test_calculate_flow_empty():
    result = calculate_flow([])
    assert result.net == 0
    assert result.buy == 0
    assert result.sell == 0
