# tests/aggregator/test_insight.py


def test_calculate_divergence_strong():
    from src.aggregator.insight import calculate_divergence

    result = calculate_divergence(
        top_ratio=1.8,
        global_ratio=0.8,
        history=[0.1, 0.2, 0.3, 0.4, 0.5],  # 历史分歧度
    )

    assert result["divergence"] == 1.0  # 1.8 - 0.8
    assert result["level"] == "strong"  # 1.0 远超历史


def test_calculate_divergence_none():
    from src.aggregator.insight import calculate_divergence

    result = calculate_divergence(
        top_ratio=1.0,
        global_ratio=1.0,
        history=[0.1, 0.2, 0.3, 0.4, 0.5],
    )

    assert result["divergence"] == 0.0
    assert result["level"] == "none"


def test_calculate_change():
    from src.aggregator.insight import calculate_change

    result = calculate_change(current=1.5, previous=1.2)

    assert result["diff"] == 0.3
    assert result["direction"] == "↑"


def test_generate_summary():
    from src.aggregator.insight import generate_summary

    data = {
        "top_ratio_change": 0.1,  # 大户加多
        "divergence": 0.5,
        "divergence_level": "strong",  # 显著分歧
        "flow_1h": 5_000_000,  # 资金流入
        "liq_long_ratio": 0.3,  # 空头承压
    }

    summary = generate_summary(data)

    assert "大户加多" in summary
    assert "分歧" in summary
    assert "资金流入" in summary
    assert "空头承压" in summary
