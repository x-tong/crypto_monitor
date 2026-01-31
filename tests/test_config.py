# tests/test_config.py
from pathlib import Path

from src.config import load_config


def test_load_config_from_yaml(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
exchanges:
  binance:
    enabled: true
  okx:
    enabled: true

symbols:
  - BTC/USDT:USDT
  - ETH/USDT:USDT

thresholds:
  default_usd: 100000
  percentile: 95
  update_interval_hours: 1

intervals:
  oi_fetch_minutes: 5
  indicator_fetch_minutes: 5
  report_hours: 8
  cleanup_hours: 24

alerts:
  whale_flow:
    enabled: true
    threshold_usd: 10000000
  oi_change:
    enabled: true
    threshold_pct: 3
  liquidation:
    enabled: true
    threshold_usd: 20000000

telegram:
  bot_token: "test_token"
  chat_id: "test_chat"

database:
  path: "data/monitor.db"
  retention_days: 7

price_alerts:
  cooldown_minutes: 60

percentile:
  window_days: 7
  update_interval_minutes: 60

percentile_levels:
  normal_below: 75
  warning_below: 90
""")

    config = load_config(config_file)

    assert config.exchanges.binance.enabled is True
    assert config.symbols == ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    assert config.thresholds.default_usd == 100000
    assert config.alerts.whale_flow.threshold_usd == 10000000
    assert config.telegram.bot_token == "test_token"
    assert config.price_alerts.cooldown_minutes == 60
    assert config.percentile_levels.normal_below == 75


def test_load_insight_config(tmp_path):
    from src.config import load_config

    config_content = """
exchanges:
  binance:
    enabled: true
  okx:
    enabled: true

symbols:
  - BTC/USDT:USDT

thresholds:
  default_usd: 100000
  percentile: 95
  update_interval_hours: 1

intervals:
  oi_fetch_minutes: 5
  indicator_fetch_minutes: 5
  report_hours: 8
  cleanup_hours: 24

alerts:
  whale_flow:
    enabled: true
    threshold_usd: 10000000
  oi_change:
    enabled: true
    threshold_pct: 3
  liquidation:
    enabled: true
    threshold_usd: 20000000

telegram:
  bot_token: "test"
  chat_id: "123"

database:
  path: "data/test.db"
  retention_days: 7

price_alerts:
  cooldown_minutes: 60

percentile:
  window_days: 7
  update_interval_minutes: 60

percentile_levels:
  normal_below: 75
  warning_below: 90

insight:
  enabled: true
  divergence:
    mild_percentile: 75
    strong_percentile: 90
  alerts:
    divergence_spike: true
    whale_flip: true
    flow_reversal: true
    flow_threshold_usd: 5000000
    cooldown_minutes: 30
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(config_file)

    assert config.insight.enabled is True
    assert config.insight.divergence.mild_percentile == 75
    assert config.insight.alerts.flow_threshold_usd == 5000000
