# tests/collector/test_indicator_fetcher.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client.models import FundingRate, Kline, LongShortRatio, OpenInterest, TakerRatio
from src.collector.indicator_fetcher import IndicatorFetcher


@pytest.mark.asyncio
async def test_fetch_all_oi():
    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    mock_oi = OpenInterest(symbol="BTCUSDT", open_interest=50000.0, timestamp=1706600000000)
    mock_kline = Kline(
        open_time=1706600000000,
        open=100000.0,
        high=100500.0,
        low=99500.0,
        close=100000.0,
        volume=1000.0,
        close_time=1706603599999,
    )

    mock_client = MagicMock()
    mock_client.get_open_interest = AsyncMock(return_value=mock_oi)
    mock_client.get_klines = AsyncMock(return_value=[mock_kline])

    fetcher._client = mock_client
    results = await fetcher.fetch_all_oi()

    assert len(results) == 1
    assert results[0].open_interest == 50000.0
    assert results[0].open_interest_usd == 5000000000.0  # 50000 * 100000


@pytest.mark.asyncio
async def test_fetch_indicators():
    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    mock_funding = FundingRate(symbol="BTCUSDT", funding_rate=0.0001, funding_time=1706600000000)
    mock_kline = Kline(
        open_time=1706600000000,
        open=100000.0,
        high=100500.0,
        low=99500.0,
        close=100000.0,
        volume=1000.0,
        close_time=1706603599999,
    )
    mock_ls = LongShortRatio(
        symbol="BTCUSDT",
        long_ratio=0.55,
        short_ratio=0.45,
        long_short_ratio=1.22,
        timestamp=1706600000000,
    )

    mock_client = MagicMock()
    mock_client.get_funding_rate = AsyncMock(return_value=mock_funding)
    mock_client.get_klines = AsyncMock(return_value=[mock_kline])
    mock_client.get_global_long_short_ratio = AsyncMock(return_value=mock_ls)

    fetcher._client = mock_client
    result = await fetcher.fetch_indicators("BTC/USDT:USDT")

    assert result is not None
    assert result.funding_rate == 0.01  # 0.0001 * 100
    assert result.long_short_ratio == 1.22
    assert result.futures_price == 100000.0


@pytest.mark.asyncio
async def test_fetch_market_indicators():
    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    mock_top_account = LongShortRatio(
        symbol="BTCUSDT",
        long_ratio=0.6,
        short_ratio=0.4,
        long_short_ratio=1.5,
        timestamp=1706600000000,
    )
    mock_top_position = LongShortRatio(
        symbol="BTCUSDT",
        long_ratio=0.62,
        short_ratio=0.38,
        long_short_ratio=1.6,
        timestamp=1706600000000,
    )
    mock_global = LongShortRatio(
        symbol="BTCUSDT",
        long_ratio=0.47,
        short_ratio=0.53,
        long_short_ratio=0.9,
        timestamp=1706600000000,
    )
    mock_taker = TakerRatio(
        symbol="BTCUSDT",
        buy_sell_ratio=1.1,
        buy_vol=5000.0,
        sell_vol=4545.0,
        timestamp=1706600000000,
    )

    mock_client = MagicMock()
    mock_client.get_top_long_short_account_ratio = AsyncMock(return_value=mock_top_account)
    mock_client.get_top_long_short_position_ratio = AsyncMock(return_value=mock_top_position)
    mock_client.get_global_long_short_ratio = AsyncMock(return_value=mock_global)
    mock_client.get_taker_long_short_ratio = AsyncMock(return_value=mock_taker)

    fetcher._client = mock_client
    result = await fetcher.fetch_market_indicators("BTC/USDT:USDT")

    assert result is not None
    assert result.top_account_ratio == 1.5
    assert result.top_position_ratio == 1.6
    assert result.global_account_ratio == 0.9
    assert result.taker_buy_sell_ratio == 1.1


@pytest.mark.asyncio
async def test_to_ws_symbol():
    fetcher = IndicatorFetcher(symbols=["BTC/USDT:USDT"])

    assert fetcher._to_ws_symbol("BTC/USDT:USDT") == "BTCUSDT"
    assert fetcher._to_ws_symbol("ETH/USDT:USDT") == "ETHUSDT"
