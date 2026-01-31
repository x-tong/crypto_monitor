"""Binance API 数据模型"""

from dataclasses import dataclass


@dataclass
class Kline:
    """K 线数据"""

    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int


@dataclass
class OpenInterest:
    """持仓量数据"""

    symbol: str
    open_interest: float
    timestamp: int


@dataclass
class FundingRate:
    """资金费率数据"""

    symbol: str
    funding_rate: float
    funding_time: int


@dataclass
class LongShortRatio:
    """多空比数据"""

    symbol: str
    long_ratio: float
    short_ratio: float
    long_short_ratio: float
    timestamp: int


@dataclass
class TakerRatio:
    """Taker 买卖比数据"""

    symbol: str
    buy_sell_ratio: float
    buy_vol: float
    sell_vol: float
    timestamp: int
