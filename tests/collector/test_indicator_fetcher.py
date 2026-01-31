# tests/collector/test_indicator_fetcher.py
from unittest.mock import AsyncMock, MagicMock


async def test_fetch_oi():
    from src.collector.indicator_fetcher import IndicatorFetcher

    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    # Mock ccxt exchange
    mock_exchange = MagicMock()
    mock_exchange.fetch_open_interest = AsyncMock(
        return_value={
            "symbol": "BTC/USDT:USDT",
            "openInterestAmount": 50000.0,
            "openInterestValue": 5000000000.0,
            "timestamp": 1706600000000,
        }
    )

    fetcher.binance = mock_exchange

    result = await fetcher._fetch_oi("binance", "BTC/USDT:USDT")

    assert result is not None
    assert result.open_interest == 50000.0
    assert result.open_interest_usd == 5000000000.0


async def test_fetch_oi_calculates_value_from_price():
    """When openInterestValue is None, calculate from amount * price."""
    from src.collector.indicator_fetcher import IndicatorFetcher

    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    mock_exchange = MagicMock()
    mock_exchange.fetch_open_interest = AsyncMock(
        return_value={
            "symbol": "BTC/USDT:USDT",
            "openInterestAmount": 100.0,
            "openInterestValue": None,  # Binance doesn't return this
            "timestamp": 1706600000000,
        }
    )
    mock_exchange.fetch_ticker = AsyncMock(
        return_value={"last": 50000.0}  # Price for calculation
    )

    fetcher.binance = mock_exchange

    result = await fetcher._fetch_oi("binance", "BTC/USDT:USDT")
    assert result is not None
    assert result.open_interest == 100.0
    assert result.open_interest_usd == 5000000.0  # 100 * 50000


async def test_fetch_oi_returns_none_when_amount_missing():
    """When openInterestAmount is None, return None."""
    from src.collector.indicator_fetcher import IndicatorFetcher

    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    mock_exchange = MagicMock()
    mock_exchange.fetch_open_interest = AsyncMock(
        return_value={
            "symbol": "BTC/USDT:USDT",
            "openInterestAmount": None,
            "openInterestValue": 5000000.0,
            "timestamp": 1706600000000,
        }
    )

    fetcher.binance = mock_exchange

    result = await fetcher._fetch_oi("binance", "BTC/USDT:USDT")
    assert result is None


async def test_fetch_market_indicators():
    from unittest.mock import AsyncMock, MagicMock

    from src.collector.indicator_fetcher import IndicatorFetcher

    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    mock_exchange = MagicMock()

    # Mock 大户账户多空比
    mock_exchange.fetch_long_short_ratio_history = AsyncMock(
        return_value=[{"longShortRatio": 1.5, "timestamp": 1706600000000}]
    )

    # Mock 大户持仓多空比
    mock_exchange.fapiDataGetTopLongShortPositionRatio = AsyncMock(
        return_value=[{"longShortRatio": "1.6", "timestamp": "1706600000000"}]
    )

    # Mock 散户账户多空比
    mock_exchange.fapiDataGetGlobalLongShortAccountRatio = AsyncMock(
        return_value=[{"longShortRatio": "0.9", "timestamp": "1706600000000"}]
    )

    # Mock 主动买卖比
    mock_exchange.fapiDataGetTakerlongshortRatio = AsyncMock(
        return_value=[{"buySellRatio": "1.1", "timestamp": "1706600000000"}]
    )

    fetcher.binance = mock_exchange

    result = await fetcher.fetch_market_indicators("BTC/USDT:USDT")

    assert result is not None
    assert result.top_account_ratio == 1.5
    assert result.top_position_ratio == 1.6
    assert result.global_account_ratio == 0.9
    assert result.taker_buy_sell_ratio == 1.1
