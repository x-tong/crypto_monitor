# src/config.py
from pathlib import Path

import yaml
from pydantic import BaseModel


class ExchangeConfig(BaseModel):
    enabled: bool = True


class ExchangesConfig(BaseModel):
    binance: ExchangeConfig = ExchangeConfig()
    okx: ExchangeConfig = ExchangeConfig()


class ThresholdsConfig(BaseModel):
    default_usd: float = 100000
    percentile: int = 95
    update_interval_hours: int = 1


class IntervalsConfig(BaseModel):
    oi_fetch_minutes: int = 5
    indicator_fetch_minutes: int = 5
    report_hours: int = 8
    cleanup_hours: int = 24


class AlertConfig(BaseModel):
    enabled: bool = True
    threshold_usd: float | None = None
    threshold_pct: float | None = None


class AlertsConfig(BaseModel):
    whale_flow: AlertConfig = AlertConfig(threshold_usd=10000000)
    oi_change: AlertConfig = AlertConfig(threshold_pct=3)
    liquidation: AlertConfig = AlertConfig(threshold_usd=20000000)


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str


class DatabaseConfig(BaseModel):
    path: str = "data/monitor.db"
    retention_days: int = 7


class PriceAlertsConfig(BaseModel):
    cooldown_minutes: int = 60


class PercentileConfig(BaseModel):
    window_days: int = 7
    update_interval_minutes: int = 60


class PercentileLevelsConfig(BaseModel):
    normal_below: int = 75
    warning_below: int = 90


class DivergenceConfig(BaseModel):
    mild_percentile: int = 75
    strong_percentile: int = 90


class InsightAlertsConfig(BaseModel):
    divergence_spike: bool = True
    whale_flip: bool = True
    flow_reversal: bool = True
    flow_threshold_usd: int = 5_000_000
    cooldown_minutes: int = 30


class InsightConfig(BaseModel):
    enabled: bool = True
    divergence: DivergenceConfig = DivergenceConfig()
    alerts: InsightAlertsConfig = InsightAlertsConfig()


class Config(BaseModel):
    exchanges: ExchangesConfig = ExchangesConfig()
    symbols: list[str] = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    thresholds: ThresholdsConfig = ThresholdsConfig()
    intervals: IntervalsConfig = IntervalsConfig()
    alerts: AlertsConfig = AlertsConfig()
    telegram: TelegramConfig
    database: DatabaseConfig = DatabaseConfig()
    price_alerts: PriceAlertsConfig = PriceAlertsConfig()
    percentile: PercentileConfig = PercentileConfig()
    percentile_levels: PercentileLevelsConfig = PercentileLevelsConfig()
    insight: InsightConfig = InsightConfig()


def load_config(path: Path) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config(**data)
