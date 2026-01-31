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
