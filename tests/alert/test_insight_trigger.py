# tests/alert/test_insight_trigger.py


def test_detect_divergence_spike():
    from src.alert.insight_trigger import check_insight_alerts

    current = {
        "divergence_level": "strong",
        "top_ratio": 1.5,
        "flow_1h": 100,
        "taker_ratio_pct": 50,
    }
    previous = {
        "divergence_level": "none",
        "top_ratio": 1.4,
        "flow_1h": 50,
        "taker_ratio_pct": 50,
    }

    alerts = check_insight_alerts(current, previous)

    assert len(alerts) == 1
    assert alerts[0].type == "divergence_spike"


def test_detect_whale_flip():
    from src.alert.insight_trigger import check_insight_alerts

    current = {
        "divergence_level": "none",
        "top_ratio": 1.1,
        "flow_1h": 100,
        "taker_ratio_pct": 50,
    }
    previous = {
        "divergence_level": "none",
        "top_ratio": 0.9,
        "flow_1h": 50,
        "taker_ratio_pct": 50,
    }

    alerts = check_insight_alerts(current, previous)

    assert len(alerts) == 1
    assert alerts[0].type == "whale_flip"


def test_detect_flow_reversal():
    from src.alert.insight_trigger import check_insight_alerts

    current = {
        "divergence_level": "none",
        "top_ratio": 1.0,
        "flow_1h": 6_000_000,
        "taker_ratio_pct": 50,
    }
    previous = {
        "divergence_level": "none",
        "top_ratio": 1.0,
        "flow_1h": -1_000_000,
        "taker_ratio_pct": 50,
    }

    alerts = check_insight_alerts(current, previous, flow_threshold=5_000_000)

    assert len(alerts) == 1
    assert alerts[0].type == "flow_reversal"


def test_no_alerts_when_stable():
    from src.alert.insight_trigger import check_insight_alerts

    current = {
        "divergence_level": "none",
        "top_ratio": 1.0,
        "flow_1h": 100,
        "taker_ratio_pct": 50,
    }
    previous = {
        "divergence_level": "none",
        "top_ratio": 1.0,
        "flow_1h": 50,
        "taker_ratio_pct": 50,
    }

    alerts = check_insight_alerts(current, previous)

    assert len(alerts) == 0
