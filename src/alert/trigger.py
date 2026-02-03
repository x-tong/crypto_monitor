# src/alert/trigger.py
from dataclasses import dataclass
from enum import Enum


class AlertLevel(Enum):
    OBSERVE = "observe"
    IMPORTANT = "important"


@dataclass
class TieredAlert:
    level: AlertLevel
    dimensions: list[tuple[str, float]]  # [(维度名, 百分位), ...]


def check_tiered_alerts(
    percentiles: dict[str, float],
    threshold: float = 90,
    min_dimensions: int = 3,
) -> list[TieredAlert]:
    """检查分级告警

    Args:
        percentiles: 各维度的百分位 {维度名: 百分位}
        threshold: 极端阈值 (默认 P90)
        min_dimensions: 触发重要提醒的最少维度数

    Returns:
        告警列表
    """
    extreme = [(name, p) for name, p in percentiles.items() if p > threshold]

    if not extreme:
        return []

    if len(extreme) >= min_dimensions:
        return [TieredAlert(level=AlertLevel.IMPORTANT, dimensions=extreme)]
    else:
        return [TieredAlert(level=AlertLevel.OBSERVE, dimensions=extreme)]
