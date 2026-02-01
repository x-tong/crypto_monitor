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


@dataclass
class ExtremeEvent:
    id: int | None
    symbol: str  # BTC / ETH
    dimension: str  # flow_1h / oi_change_1h / funding_rate / ...
    window_days: int  # 7 / 30 / 90
    triggered_at: int  # 触发时间 (ms)
    value: float  # 触发时的值
    percentile: float  # 百分位
    price_at_trigger: float  # 触发时价格
    price_4h: float | None  # 4h 后价格
    price_12h: float | None  # 12h 后价格
    price_24h: float | None  # 24h 后价格
    price_48h: float | None  # 48h 后价格
