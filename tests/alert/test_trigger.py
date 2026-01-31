# tests/alert/test_trigger.py
from src.aggregator.flow import FlowResult
from src.aggregator.liquidation import LiqStats
from src.alert.trigger import AlertType, check_alerts


def test_check_whale_flow_alert():
    flow = FlowResult(net=15000000, buy=20000000, sell=5000000)
    alerts = check_alerts(
        flow=flow,
        oi_change=1.0,
        liq_stats=LiqStats(),
        thresholds={"whale_flow_usd": 10000000, "oi_change_pct": 3, "liq_usd": 20000000},
    )

    assert len(alerts) == 1
    assert alerts[0].type == AlertType.WHALE_FLOW


def test_check_oi_alert():
    alerts = check_alerts(
        flow=FlowResult(),
        oi_change=4.5,
        liq_stats=LiqStats(),
        thresholds={"whale_flow_usd": 10000000, "oi_change_pct": 3, "liq_usd": 20000000},
    )

    assert len(alerts) == 1
    assert alerts[0].type == AlertType.OI_CHANGE


def test_check_liquidation_alert():
    alerts = check_alerts(
        flow=FlowResult(),
        oi_change=1.0,
        liq_stats=LiqStats(long=25000000, short=5000000),
        thresholds={"whale_flow_usd": 10000000, "oi_change_pct": 3, "liq_usd": 20000000},
    )

    assert len(alerts) == 1
    assert alerts[0].type == AlertType.LIQUIDATION


def test_check_no_alerts():
    alerts = check_alerts(
        flow=FlowResult(net=5000000),
        oi_change=1.0,
        liq_stats=LiqStats(long=5000000),
        thresholds={"whale_flow_usd": 10000000, "oi_change_pct": 3, "liq_usd": 20000000},
    )

    assert len(alerts) == 0


def test_observe_alert_single_dimension():
    """单维度极端触发观察提醒"""
    from src.alert.trigger import AlertLevel, check_tiered_alerts

    percentiles = {
        "flow": 92,  # > 90
        "oi_change": 60,
        "liquidation": 70,
        "funding_rate": 50,
        "global_ls": 65,
        "top_position_ls": 55,
        "taker_ratio": 45,
    }

    alerts = check_tiered_alerts(percentiles, threshold=90, min_dimensions=3)

    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.OBSERVE
    assert "flow" in [d[0] for d in alerts[0].dimensions]


def test_important_alert_multi_dimension():
    """多维度极端触发重要提醒"""
    from src.alert.trigger import AlertLevel, check_tiered_alerts

    percentiles = {
        "flow": 95,
        "oi_change": 92,
        "liquidation": 94,
        "funding_rate": 50,
        "global_ls": 65,
        "top_position_ls": 55,
        "taker_ratio": 45,
    }

    alerts = check_tiered_alerts(percentiles, threshold=90, min_dimensions=3)

    assert len(alerts) == 1
    assert alerts[0].level == AlertLevel.IMPORTANT
    assert len(alerts[0].dimensions) == 3


def test_no_alert_when_all_normal():
    """无极端维度时不触发"""
    from src.alert.trigger import check_tiered_alerts

    percentiles = {
        "flow": 60,
        "oi_change": 50,
        "liquidation": 70,
        "funding_rate": 50,
        "global_ls": 65,
        "top_position_ls": 55,
        "taker_ratio": 45,
    }

    alerts = check_tiered_alerts(percentiles, threshold=90, min_dimensions=3)
    assert len(alerts) == 0
