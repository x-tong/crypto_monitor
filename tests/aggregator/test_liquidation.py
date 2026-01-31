# tests/aggregator/test_liquidation.py
from src.aggregator.liquidation import calculate_liquidations
from src.storage.models import Liquidation


def test_calculate_liquidations():
    liqs = [
        Liquidation(1, "binance", "BTC/USDT:USDT", 1706600000000, "sell", 99000, 1.0, 99000),
        Liquidation(2, "binance", "BTC/USDT:USDT", 1706600001000, "sell", 98500, 0.5, 49250),
        Liquidation(3, "okx", "BTC/USDT:USDT", 1706600002000, "buy", 101000, 0.3, 30300),
    ]

    stats = calculate_liquidations(liqs)

    assert stats.long == 148250  # sell = long liquidation
    assert stats.short == 30300  # buy = short liquidation
    assert stats.total == 178550


def test_calculate_liquidations_empty():
    stats = calculate_liquidations([])
    assert stats.long == 0
    assert stats.short == 0
    assert stats.total == 0
