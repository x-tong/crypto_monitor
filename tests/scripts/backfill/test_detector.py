# tests/scripts/backfill/test_detector.py
import pytest


def test_calculate_rolling_percentile():
    from src.scripts.backfill.detector import calculate_rolling_percentile

    # 10 个数据点，使用 5 小时窗口
    data = [(i * 3600000, float(i * 10)) for i in range(10)]  # 0, 10, 20, ..., 90

    # 在 idx=6 (value=60) 计算 5h 窗口
    # 窗口内有 idx 1-5 的数据: 10, 20, 30, 40, 50
    # 60 比 5 个值都大，百分位 = 5/5 * 100 = 100%
    pct = calculate_rolling_percentile(data, current_idx=6, window_hours=5)

    assert pct is not None
    assert pct == pytest.approx(100.0, abs=1)


def test_calculate_rolling_percentile_insufficient_data():
    from src.scripts.backfill.detector import calculate_rolling_percentile

    data = [(i * 3600000, float(i)) for i in range(5)]  # 只有 5 小时数据

    # 7 天窗口需要 168 小时，数据不足
    pct = calculate_rolling_percentile(data, current_idx=4, window_hours=168)

    assert pct is None


def test_detect_extreme_events():
    from src.scripts.backfill.detector import detect_extreme_events

    # 100 个数据点，最后 5 个是极端值
    data = [(i * 3600000, float(i)) for i in range(100)]
    # 修改最后几个为极端值
    data[95] = (95 * 3600000, 1000.0)
    data[97] = (97 * 3600000, 1000.0)
    data[99] = (99 * 3600000, 1000.0)

    events = detect_extreme_events(
        data,
        dimension="test_dim",
        symbol="BTC",
        window_hours=72,  # 3 天窗口
        threshold=90,
        cooldown_hours=1,
    )

    # 应该检测到极端事件（有冷却期，可能不是 3 个）
    assert len(events) >= 1
    assert all(e["percentile"] >= 90 for e in events)
