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


def test_format_insight_report():
    from src.notifier.formatter import format_insight_report

    data = {
        "symbol": "BTC",
        "price": 83200,
        "price_change_1h": 1.2,
        "summary": "大户加多，与散户分歧，资金流入",
        # 大户 vs 散户
        "top_position_ratio": 1.52,
        "top_position_change": 0.12,
        "top_position_pct": 65,
        "global_account_ratio": 0.88,
        "global_account_change": -0.08,
        "global_account_pct": 58,
        "divergence": 0.64,
        "divergence_pct": 92,
        "divergence_level": "strong",
        # 资金动向
        "taker_ratio": 1.15,
        "taker_ratio_change": 0.05,
        "taker_ratio_pct": 62,
        "flow_1h": 5_200_000,
        "flow_1h_pct": 58,
        "flow_binance": 3_800_000,
        "flow_okx": 1_400_000,
        # 持仓 & 爆仓
        "oi_value": 18_200_000_000,
        "oi_change_1h": 1.2,
        "oi_change_1h_pct": 55,
        "liq_1h_total": 7_400_000,
        "liq_long_ratio": 0.32,
        # 情绪指标
        "funding_rate": 0.012,
        "funding_rate_pct": 48,
        "spot_perp_spread": 0.05,
        "spot_perp_spread_pct": 44,
    }

    result = format_insight_report(data)

    assert "BTC 市场洞察" in result
    assert "大户加多" in result
    assert "大户 vs 散户" in result
    assert "1.52" in result
    assert "资金动向" in result
    assert "空头承压" in result


def test_format_observe_alert():
    from src.notifier.formatter import format_observe_alert

    data = {
        "symbol": "BTC",
        "price": 103850,
        "price_change_1h": -0.5,
        "dimensions": [("主力资金", 92, "-$8.2M")],
        "timestamp": "2026-01-30 14:32 UTC",
    }

    result = format_observe_alert(data)
    assert "📢 BTC 观察提醒" in result
    assert "主力资金" in result
    assert "🔴 P92" in result
    assert "-$8.2M" in result


def test_format_important_alert():
    from src.notifier.formatter import format_important_alert

    data = {
        "symbol": "BTC",
        "price": 101200,
        "price_change_1h": -2.8,
        "dimensions": [
            ("主力资金", 96, "-$15.2M"),
            ("OI变化", 94, "+4.2%"),
            ("爆仓", 95, "$35M"),
        ],
        "timestamp": "2026-01-30 14:32 UTC",
    }

    result = format_important_alert(data)
    assert "🚨 BTC 重要提醒" in result
    assert "3 维度共振" in result
    assert "主力资金" in result
    assert "OI变化" in result
    assert "爆仓" in result
