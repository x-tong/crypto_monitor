# tests/alert/test_price_monitor.py
import time

from src.alert.price_monitor import check_price_alerts
from src.storage.models import PriceAlert


def test_breakout_from_below():
    alerts = [
        PriceAlert(id=1, symbol="BTC", price=100000, last_position="below", last_triggered_at=None)
    ]
    current_price = 100500

    results = check_price_alerts(alerts, current_price, cooldown_seconds=3600)

    assert len(results) == 1
    assert results[0].alert_id == 1
    assert results[0].type == "breakout"
    assert results[0].price == 100000


def test_breakdown_from_above():
    alerts = [
        PriceAlert(id=1, symbol="BTC", price=100000, last_position="above", last_triggered_at=None)
    ]
    current_price = 99500

    results = check_price_alerts(alerts, current_price, cooldown_seconds=3600)

    assert len(results) == 1
    assert results[0].type == "breakdown"


def test_cooldown_blocks_trigger():
    now = int(time.time())
    alerts = [
        PriceAlert(
            id=1,
            symbol="BTC",
            price=100000,
            last_position="below",
            last_triggered_at=now - 1800,  # 30 分钟前触发
        )
    ]
    current_price = 100500

    results = check_price_alerts(alerts, current_price, cooldown_seconds=3600)

    assert len(results) == 0  # 冷却中


def test_no_trigger_same_side():
    alerts = [
        PriceAlert(id=1, symbol="BTC", price=100000, last_position="above", last_triggered_at=None)
    ]
    current_price = 100500  # 仍在上方

    results = check_price_alerts(alerts, current_price, cooldown_seconds=3600)

    assert len(results) == 0
