# src/aggregator/percentile.py


def calculate_percentile(value: float, history: list[float]) -> float:
    if not history:
        return 50.0
    count_below = sum(1 for h in history if h < abs(value))
    return count_below / len(history) * 100


def get_level_emoji(percentile: float) -> str:
    if percentile < 75:
        return "🟢"
    elif percentile < 90:
        return "🟡"
    else:
        return "🔴"


def calculate_percentile_multi_window(
    value: float,
    history: list[float],
    windows: list[int] | None = None,
) -> dict[str, float | None]:
    """
    计算多窗口百分位

    Args:
        value: 当前值
        history: 历史数据列表（按时间顺序，每天一个值）
        windows: 窗口大小列表（天）

    Returns:
        {窗口名: 百分位} 字典，数据不足时为 None
    """
    if windows is None:
        windows = [7, 30, 90]
    result: dict[str, float | None] = {}
    for window in windows:
        key = f"{window}d"
        if len(history) < window:
            result[key] = None
        else:
            window_data = history[-window:]
            result[key] = calculate_percentile(value, window_data)
    return result


def format_multi_window_percentile(percentiles: dict[str, float | None]) -> str:
    """格式化多窗口百分位显示"""
    parts = []
    for key in ["7d", "30d", "90d"]:
        pct = percentiles.get(key)
        if pct is not None:
            parts.append(f"P{int(round(pct))}({key})")
    return " / ".join(parts)
