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
