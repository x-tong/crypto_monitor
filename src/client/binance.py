"""Binance Futures API 客户端"""

from dataclasses import dataclass


@dataclass
class BinanceClient:
    """Binance Futures API 客户端"""

    base_url: str = "https://fapi.binance.com"
    ws_url: str = "wss://fstream.binance.com"
