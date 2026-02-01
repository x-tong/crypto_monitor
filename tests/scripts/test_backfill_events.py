# tests/scripts/test_backfill_events.py
import pytest


def test_parse_args():
    from src.scripts.backfill_events import parse_args

    args = parse_args(["--days", "365", "--symbol", "BTC"])
    assert args.days == 365
    assert args.symbol == "BTC"


def test_parse_args_defaults():
    from src.scripts.backfill_events import parse_args

    args = parse_args([])
    assert args.days == 365
    assert args.symbol is None  # 默认处理所有 symbol


async def test_calculate_historical_percentile():
    from src.scripts.backfill_events import calculate_historical_percentile

    # 模拟 30 天历史数据
    history = [float(i) for i in range(1, 31)]  # 1-30
    current_idx = 25  # 当前在第 26 天

    # 使用 7 天窗口
    result = calculate_historical_percentile(
        history, current_idx, value=28.0, window_days=7
    )

    # 窗口数据: 20-26，value=28 超过所有值
    assert result == 100.0


async def test_calculate_historical_percentile_insufficient_data():
    from src.scripts.backfill_events import calculate_historical_percentile

    history = [1.0, 2.0, 3.0]
    result = calculate_historical_percentile(
        history, current_idx=2, value=2.5, window_days=7
    )
    assert result is None  # 数据不足
