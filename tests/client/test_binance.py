from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client.binance import BinanceAPIError, BinanceClient


def test_binance_client_init():
    client = BinanceClient()
    assert client.base_url == "https://fapi.binance.com"
    assert client.ws_url == "wss://fstream.binance.com"


def test_binance_client_custom_urls():
    client = BinanceClient(
        base_url="https://custom.api.com",
        ws_url="wss://custom.ws.com",
    )
    assert client.base_url == "https://custom.api.com"
    assert client.ws_url == "wss://custom.ws.com"


@pytest.mark.asyncio
async def test_request_get():
    client = BinanceClient()

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"symbol": "BTCUSDT"})

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    result = await client._request("GET", "/fapi/v1/ticker/price", {"symbol": "BTCUSDT"})
    assert result == {"symbol": "BTCUSDT"}
    mock_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_request_handles_error():
    client = BinanceClient()

    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"code": -1121, "msg": "Invalid symbol"}')

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    with pytest.raises(BinanceAPIError, match="Invalid symbol"):
        await client._request("GET", "/fapi/v1/ticker/price", {"symbol": "INVALID"})


@pytest.mark.asyncio
async def test_get_klines():
    from src.client.models import Kline

    client = BinanceClient()

    mock_data = [
        [1704067200000, "42000.0", "42500.0", "41800.0", "42300.0", "1000.0", 1704070799999]
    ]
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    klines = await client.get_klines("BTCUSDT", "1h", limit=1)
    assert len(klines) == 1
    assert isinstance(klines[0], Kline)
    assert klines[0].close == 42300.0


@pytest.mark.asyncio
async def test_get_open_interest():
    from src.client.models import OpenInterest

    client = BinanceClient()

    mock_data = {"symbol": "BTCUSDT", "openInterest": "50000.123", "time": 1704067200000}
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    oi = await client.get_open_interest("BTCUSDT")
    assert isinstance(oi, OpenInterest)
    assert oi.symbol == "BTCUSDT"
    assert oi.open_interest == 50000.123


@pytest.mark.asyncio
async def test_get_open_interest_hist():
    client = BinanceClient()

    mock_data = [
        {"symbol": "BTCUSDT", "sumOpenInterest": "50000.0", "timestamp": 1704067200000},
        {"symbol": "BTCUSDT", "sumOpenInterest": "51000.0", "timestamp": 1704070800000},
    ]
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    oi_list = await client.get_open_interest_hist("BTCUSDT", "1h", limit=2)
    assert len(oi_list) == 2
    assert oi_list[0].open_interest == 50000.0
    assert oi_list[1].open_interest == 51000.0


@pytest.mark.asyncio
async def test_get_funding_rate():
    from src.client.models import FundingRate

    client = BinanceClient()

    mock_data = [{"symbol": "BTCUSDT", "fundingRate": "0.0001", "fundingTime": 1704067200000}]
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    fr = await client.get_funding_rate("BTCUSDT")
    assert isinstance(fr, FundingRate)
    assert fr.funding_rate == 0.0001


@pytest.mark.asyncio
async def test_get_global_long_short_ratio():
    from src.client.models import LongShortRatio

    client = BinanceClient()

    mock_data = [
        {
            "symbol": "BTCUSDT",
            "longAccount": "0.55",
            "shortAccount": "0.45",
            "longShortRatio": "1.22",
            "timestamp": 1704067200000,
        }
    ]
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    ratio = await client.get_global_long_short_ratio("BTCUSDT", "1h")
    assert isinstance(ratio, LongShortRatio)
    assert ratio.long_ratio == 0.55
    assert ratio.short_ratio == 0.45
    assert ratio.long_short_ratio == 1.22


@pytest.mark.asyncio
async def test_get_top_long_short_account_ratio():
    client = BinanceClient()

    mock_data = [
        {
            "symbol": "BTCUSDT",
            "longAccount": "0.60",
            "shortAccount": "0.40",
            "longShortRatio": "1.50",
            "timestamp": 1704067200000,
        }
    ]
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    ratio = await client.get_top_long_short_account_ratio("BTCUSDT", "1h")
    assert ratio.long_ratio == 0.60


@pytest.mark.asyncio
async def test_get_top_long_short_position_ratio():
    client = BinanceClient()

    mock_data = [
        {
            "symbol": "BTCUSDT",
            "longAccount": "0.65",
            "shortAccount": "0.35",
            "longShortRatio": "1.86",
            "timestamp": 1704067200000,
        }
    ]
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    ratio = await client.get_top_long_short_position_ratio("BTCUSDT", "1h")
    assert ratio.long_ratio == 0.65


@pytest.mark.asyncio
async def test_get_taker_long_short_ratio():
    from src.client.models import TakerRatio

    client = BinanceClient()

    mock_data = [
        {
            "symbol": "BTCUSDT",
            "buySellRatio": "1.10",
            "buyVol": "5000.0",
            "sellVol": "4545.45",
            "timestamp": 1704067200000,
        }
    ]
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    client._session = mock_session

    ratio = await client.get_taker_long_short_ratio("BTCUSDT", "1h")
    assert isinstance(ratio, TakerRatio)
    assert ratio.buy_sell_ratio == 1.10
    assert ratio.buy_vol == 5000.0
