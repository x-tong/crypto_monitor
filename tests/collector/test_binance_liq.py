# tests/collector/test_binance_liq.py
from unittest.mock import AsyncMock

from src.collector.binance_liq import BinanceLiquidationCollector


def test_parse_liquidation_message():
    collector = BinanceLiquidationCollector(
        symbols=["BTC/USDT:USDT"],
        on_liquidation=AsyncMock(),
    )

    # Binance forceOrder 原始格式
    message = {
        "e": "forceOrder",
        "E": 1706600000000,
        "o": {
            "s": "BTCUSDT",
            "S": "SELL",
            "q": "1.5",
            "p": "99000",
            "ap": "98500",
            "X": "FILLED",
            "T": 1706600000000,
        },
    }

    result = collector._parse_liquidation(message)

    assert result is not None
    assert result.exchange == "binance"
    assert result.symbol == "BTC/USDT:USDT"
    assert result.side == "sell"
    assert result.quantity == 1.5
    assert result.value_usd == 147750.0  # 1.5 * 98500
