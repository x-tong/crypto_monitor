# tests/scripts/backfill/test_downloader.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path


def test_get_monthly_range():
    from src.scripts.backfill.downloader import get_monthly_range

    # 365 天前到现在
    months = get_monthly_range(365)
    assert len(months) >= 12
    assert all(len(m) == 7 for m in months)  # YYYY-MM 格式


def test_build_download_url():
    from src.scripts.backfill.downloader import build_download_url

    url = build_download_url("BTCUSDT", "aggTrades", "2025-01")
    assert "data.binance.vision" in url
    assert "BTCUSDT" in url
    assert "aggTrades" in url
    assert "2025-01" in url


async def test_download_file_creates_cache_dir(tmp_path):
    from src.scripts.backfill.downloader import Downloader

    downloader = Downloader(cache_dir=tmp_path)

    # Mock HTTP response with proper async context manager
    with patch("src.scripts.backfill.downloader.aiohttp.ClientSession") as mock_session:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"test data")

        # session.get() returns an async context manager
        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)

        # session is also an async context manager
        mock_session_instance = MagicMock()
        mock_session_instance.get = MagicMock(return_value=mock_get_cm)

        mock_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session_instance
        )
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await downloader.download_file(
            "https://example.com/test.zip", tmp_path / "test.zip"
        )

    assert (tmp_path / "test.zip").exists()
