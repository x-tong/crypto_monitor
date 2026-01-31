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
