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
