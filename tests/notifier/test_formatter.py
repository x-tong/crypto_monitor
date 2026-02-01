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
        # 大户 vs 散户
        "top_position_ratio": 1.52,  # 60% 多
        "top_position_change": 0.12,
        "top_position_pct": 65,
        "global_account_ratio": 0.88,  # 47% 多
        "global_account_change": -0.08,
        "global_account_pct": 58,
        # 资金动向
        "taker_ratio": 1.15,
        "taker_ratio_change": 0.05,
        "taker_ratio_pct": 62,
        "flow_1h": 5_200_000,
        "flow_1h_pct": 58,
        "flow_binance": 3_800_000,
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
    assert "多空对比" in result
    assert "60% 多" in result  # 大户 1.52 -> 60%
    assert "资金动向" in result
    assert "空头承压" in result
    assert "各维度正常" in result  # 无异常


def test_format_observe_alert():
    from src.notifier.formatter import format_observe_alert

    data = {
        "symbol": "BTC",
        "price": 103850,
        "price_change_1h": -0.5,
        "dimensions": [("散户持仓", 92)],
        "timestamp": "2026-01-30 14:32 UTC",
        "top_position_ratio": 1.86,  # 65% 多
        "top_position_pct": 50,
        "global_account_ratio": 2.57,  # 72% 多
        "global_account_pct": 92,
        "flow_net": -8200000,
        "oi_change": 0.5,
        "liq_total": 5000000,
        "funding_rate": 0.0001,
    }

    result = format_observe_alert(data)
    assert "📢 BTC 观察提醒" in result
    assert "持仓多空比" in result
    assert "散户" in result
    assert "大户" in result
    assert "P92" in result


def test_format_important_alert():
    from src.notifier.formatter import format_important_alert

    data = {
        "symbol": "BTC",
        "price": 101200,
        "price_change_1h": -2.8,
        "dimensions": [
            ("主力资金", 96),
            ("OI变化", 94),
            ("爆仓", 95),
        ],
        "timestamp": "2026-01-30 14:32 UTC",
        "top_position_ratio": 1.86,
        "top_position_pct": 50,
        "global_account_ratio": 2.57,
        "global_account_pct": 70,
        "flow_net": -15200000,
        "oi_change": 4.2,
        "liq_total": 35000000,
        "funding_rate": 0.0001,
    }

    result = format_important_alert(data)
    assert "🚨 BTC 重要提醒" in result
    assert "3 个维度" in result
    assert "主力资金" in result
    assert "OI" in result or "持仓量" in result
    assert "爆仓" in result


def test_format_history_reference_block():
    from src.notifier.formatter import format_history_reference_block

    stats = {
        "7d": {
            "count": 20,
            "stats": {
                "24h": {"up_pct": 45.0, "down_pct": 55.0, "avg_change": -1.2},
            },
        },
        "30d": {
            "count": 15,
            "stats": {
                "24h": {"up_pct": 35.0, "down_pct": 65.0, "avg_change": -2.8},
            },
        },
    }
    latest = {
        "30d": {
            "triggered_at": 1706400000000,  # 2024-01-28
            "price_at_trigger": 82000.0,
            "change_24h": -4.8,
        }
    }

    result = format_history_reference_block(stats, latest)

    assert "7d P90+" in result
    assert "近20次" in result
    assert "45%" in result
    assert "55%" in result
    assert "30d P90+" in result
    assert "最近(30d)" in result
    assert "-4.8%" in result


def test_format_history_reference_block_insufficient_data():
    from src.notifier.formatter import format_history_reference_block

    stats = {"7d": {"count": 3, "stats": {}}}  # 少于 5 次
    latest = {}

    result = format_history_reference_block(stats, latest)

    assert "数据积累中" in result


def test_format_history_reference_block_empty():
    from src.notifier.formatter import format_history_reference_block

    result = format_history_reference_block({}, {})
    assert result == ""


def test_format_insight_report_with_history():
    from src.notifier.formatter import format_insight_report_with_history

    data = {
        "symbol": "BTC",
        "price": 82000.0,
        "price_change_1h": 0.5,
        "top_position_ratio": 1.8,
        "top_position_pct": 50.0,
        "top_position_pct_7d": 55.0,
        "top_position_pct_30d": 60.0,
        "top_position_pct_90d": 45.0,
        "top_position_change": 0.02,
        "global_account_ratio": 1.5,
        "global_account_pct": 78.0,
        "global_account_pct_7d": 80.0,
        "global_account_pct_30d": 75.0,
        "global_account_pct_90d": 70.0,
        "global_account_change": 0.01,
        "flow_1h": 47_700_000.0,
        "flow_1h_pct": 92.0,  # P90+ 触发
        "flow_1h_pct_7d": 95.0,
        "flow_1h_pct_30d": 92.0,
        "flow_1h_pct_90d": 70.0,
        "flow_binance": 47_700_000.0,
        "taker_ratio": 0.8,
        "taker_ratio_pct": 50.0,
        "taker_ratio_pct_7d": 50.0,
        "taker_ratio_pct_30d": 50.0,
        "taker_ratio_pct_90d": 50.0,
        "oi_value": 7_400_000_000.0,
        "oi_change_1h": 0.5,
        "oi_change_1h_pct": 60.0,
        "oi_change_1h_pct_7d": 60.0,
        "oi_change_1h_pct_30d": 55.0,
        "oi_change_1h_pct_90d": 50.0,
        "liq_1h_total": 500_000.0,
        "liq_long_ratio": 0.7,
        "funding_rate": 0.01,
        "funding_rate_pct": 50.0,
        "funding_rate_pct_7d": 50.0,
        "funding_rate_pct_30d": 50.0,
        "funding_rate_pct_90d": 50.0,
        "spot_perp_spread": 0.01,
        "spot_perp_spread_pct": 50.0,
        "spot_perp_spread_pct_7d": 50.0,
        "spot_perp_spread_pct_30d": 50.0,
        "spot_perp_spread_pct_90d": 50.0,
    }

    history_data = {
        "flow_1h": {
            "stats": {
                "7d": {
                    "count": 20,
                    "stats": {"24h": {"up_pct": 45.0, "down_pct": 55.0, "avg_change": -1.2}},
                },
                "30d": {
                    "count": 15,
                    "stats": {"24h": {"up_pct": 35.0, "down_pct": 65.0, "avg_change": -2.8}},
                },
            },
            "latest": {
                "30d": {"triggered_at": 1706400000000, "price_at_trigger": 82000.0, "change_24h": -4.8}
            },
        }
    }

    result = format_insight_report_with_history(data, history_data)

    assert "P95(7d) / P92(30d) / P70(90d)" in result
    assert "历史参考" in result
    assert "7d P90+" in result
