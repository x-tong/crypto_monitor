# tests/notifier/test_formatter.py
from src.notifier.formatter import format_price_alert, format_report


def test_format_report():
    data = {
        "symbol": "BTC",
        "price": 104230,
        "price_change_1h": 1.2,
        "price_change_24h": 3.5,
        "flow_1h": 5200000,
        "flow_1h_pct": 62,
        "flow_4h": 18300000,
        "flow_4h_pct": 78,
        "flow_24h": 42100000,
        "flow_24h_pct": 55,
        "flow_binance": 28000000,
        "flow_okx": 14000000,
        "oi_value": 18200000000,
        "oi_change_1h": 1.2,
        "oi_change_1h_pct": 58,
        "oi_change_4h": 2.3,
        "oi_change_4h_pct": 76,
        "oi_interpretation": "新多入场",
        "liq_1h_total": 7400000,
        "liq_1h_pct": 52,
        "liq_1h_long": 2100000,
        "liq_1h_short": 5300000,
        "liq_4h_total": 20300000,
        "liq_4h_pct": 82,
        "liq_4h_long": 8200000,
        "liq_4h_short": 12100000,
        "funding_rate": -0.01,
        "funding_rate_pct": 48,
        "long_short_ratio": 1.35,
        "long_short_ratio_pct": 62,
        "spot_perp_spread": 0.05,
        "spot_perp_spread_pct": 44,
    }

    msg = format_report(data)

    assert "BTC" in msg
    assert "$104,230" in msg
    assert "+1.2%" in msg
    assert "🟢" in msg  # P62 should be green


def test_format_price_alert_breakout():
    data = {
        "symbol": "BTC",
        "type": "breakout",
        "target_price": 100000,
        "current_price": 100150,
        "price_change_1h": 0.3,
        "flow_1h": 3200000,
        "flow_1h_pct": 62,
        "oi_change_1h": 2.8,
        "oi_change_1h_pct": 85,
        "liq_1h_total": 8500000,
        "liq_1h_pct": 58,
        "liq_1h_long": 3200000,
        "liq_1h_short": 5300000,
        "funding_rate": 0.01,
        "funding_rate_pct": 45,
    }

    msg = format_price_alert(data)

    assert "📍 BTC 突破 100000" in msg
    assert "$100,150" in msg
