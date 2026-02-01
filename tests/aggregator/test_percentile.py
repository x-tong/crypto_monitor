# tests/aggregator/test_percentile.py
from src.aggregator.percentile import calculate_percentile, get_level_emoji


def test_calculate_percentile():
    history = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    assert calculate_percentile(55, history) == 50.0  # 5 values below
    assert calculate_percentile(95, history) == 90.0  # 9 values below
    assert calculate_percentile(5, history) == 0.0  # 0 values below


def test_calculate_percentile_empty():
    assert calculate_percentile(50, []) == 50.0


def test_calculate_percentile_absolute():
    # 对于资金流向，用绝对值计算
    history = [10, 20, 30, 40, 50]
    assert calculate_percentile(-35, history) == 60.0  # abs(-35)=35, 3 values below


def test_get_level_emoji():
    assert get_level_emoji(50) == "🟢"
    assert get_level_emoji(74) == "🟢"
    assert get_level_emoji(75) == "🟡"
    assert get_level_emoji(89) == "🟡"
    assert get_level_emoji(90) == "🔴"
    assert get_level_emoji(99) == "🔴"


def test_calculate_percentile_multi_window():
    import pytest

    from src.aggregator.percentile import calculate_percentile_multi_window

    # 模拟 30 天数据，每天一个值
    history = list(range(10, 310, 10))  # 10, 20, ..., 300

    result = calculate_percentile_multi_window(
        value=250.0,
        history=history,
        windows=[7, 30],
    )
    assert "7d" in result
    assert "30d" in result
    # 7d: 最后 7 个值是 240, 250, 260, 270, 280, 290, 300
    # 250 比 240 大，所以 percentile = 1/7 * 100 = 14.3
    assert result["7d"] == pytest.approx(14.3, abs=0.1)
    # 30d: 最后 30 个值是 10, 20, ..., 300
    # 250 比 24 个值大（10-240），所以 percentile = 24/30 * 100 = 80
    assert result["30d"] == pytest.approx(80.0, abs=0.1)


def test_calculate_percentile_multi_window_short_history():
    from src.aggregator.percentile import calculate_percentile_multi_window

    # 只有 10 天数据
    history = list(range(10, 110, 10))  # 10, 20, ..., 100

    result = calculate_percentile_multi_window(
        value=75.0,
        history=history,
        windows=[7, 30, 90],
    )
    # 7d 正常计算
    assert "7d" in result
    # 30d 和 90d 数据不足，返回 None
    assert result.get("30d") is None
    assert result.get("90d") is None


def test_format_multi_window_percentile():
    from src.aggregator.percentile import format_multi_window_percentile

    percentiles = {"7d": 92.5, "30d": 85.0, "90d": 70.0}
    result = format_multi_window_percentile(percentiles)
    assert "P93(7d)" in result or "P92(7d)" in result  # 四舍五入
    assert "P85(30d)" in result
    assert "P70(90d)" in result
