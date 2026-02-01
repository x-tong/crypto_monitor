"""极端事件检测器"""

import logging
from typing import Any

from .config import COOLDOWN_HOURS, EXTREME_THRESHOLD, WINDOWS

logger = logging.getLogger(__name__)


def calculate_rolling_percentile(
    data: list[tuple[int, float]],  # [(timestamp_ms, value), ...]
    current_idx: int,
    window_hours: int,
) -> float | None:
    """
    计算滚动窗口百分位

    Args:
        data: 按时间排序的 (timestamp, value) 列表
        current_idx: 当前位置索引
        window_hours: 窗口大小（小时）

    Returns:
        百分位 (0-100)，数据不足返回 None
    """
    if current_idx < window_hours:
        return None

    # 获取窗口数据（不包含当前点，用于计算"历史"百分位）
    start_idx = max(0, current_idx - window_hours)
    window_data = [v for _, v in data[start_idx:current_idx]]

    if len(window_data) < window_hours:
        return None

    current_value = abs(data[current_idx][1])
    count_below = sum(1 for v in window_data if abs(v) < current_value)

    return count_below / len(window_data) * 100


def detect_extreme_events(
    data: list[tuple[int, float]],
    dimension: str,
    symbol: str,
    window_hours: int,
    threshold: float = EXTREME_THRESHOLD,
    cooldown_hours: int = COOLDOWN_HOURS,
) -> list[dict[str, Any]]:
    """
    检测极端事件

    Args:
        data: 按时间排序的 (timestamp, value) 列表
        dimension: 维度名称
        symbol: 交易对
        window_hours: 百分位窗口（小时）
        threshold: 极端阈值 (默认 90)
        cooldown_hours: 冷却期（小时）

    Returns:
        极端事件列表
    """
    events = []
    last_trigger_ts = 0
    cooldown_ms = cooldown_hours * 3600 * 1000

    for idx in range(window_hours, len(data)):
        ts, value = data[idx]

        # 检查冷却期
        if ts - last_trigger_ts < cooldown_ms:
            continue

        pct = calculate_rolling_percentile(data, idx, window_hours)
        if pct is None:
            continue

        if pct >= threshold:
            events.append(
                {
                    "symbol": symbol,
                    "dimension": dimension,
                    "window_days": window_hours // 24,
                    "triggered_at": ts,
                    "value": value,
                    "percentile": pct,
                }
            )
            last_trigger_ts = ts

    return events


def detect_all_windows(
    data: list[tuple[int, float]],
    dimension: str,
    symbol: str,
) -> list[dict[str, Any]]:
    """对所有窗口检测极端事件"""
    all_events = []

    for window_days, window_hours in WINDOWS.items():
        events = detect_extreme_events(
            data,
            dimension=dimension,
            symbol=symbol,
            window_hours=window_hours,
        )
        all_events.extend(events)
        logger.info(f"  {window_days}d window: {len(events)} events")

    return all_events
