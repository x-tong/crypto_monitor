import pytest
from unittest.mock import AsyncMock, MagicMock

from src.client.binance import BinanceClient, BinanceAPIError


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
    from src.client.models import OpenInterest

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
