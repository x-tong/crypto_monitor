# src/storage/models.py
from dataclasses import dataclass


@dataclass
class Trade:
    id: int | None
    exchange: str
    symbol: str
    timestamp: int
    price: float
    amount: float
    side: str
    value_usd: float


@dataclass
class Liquidation:
    id: int | None
    exchange: str
    symbol: str
    timestamp: int
    side: str
    price: float
    quantity: float
    value_usd: float


@dataclass
class OISnapshot:
    id: int | None
    exchange: str
    symbol: str
    timestamp: int
    open_interest: float
    open_interest_usd: float


@dataclass
class PriceAlert:
    id: int | None
    symbol: str
    price: float
    last_position: str | None
    last_triggered_at: int | None


@dataclass
class MarketIndicator:
    id: int | None
    symbol: str
    timestamp: int
    top_account_ratio: float  # 大户账户多空比
    top_position_ratio: float  # 大户持仓多空比
    global_account_ratio: float  # 散户账户多空比
    taker_buy_sell_ratio: float  # 主动买卖比
