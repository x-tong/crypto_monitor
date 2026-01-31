# src/alert/trigger.py
from dataclasses import dataclass
from enum import Enum

from src.aggregator.flow import FlowResult
from src.aggregator.liquidation import LiqStats


class AlertType(Enum):
    WHALE_FLOW = "whale_flow"
    OI_CHANGE = "oi_change"
    LIQUIDATION = "liquidation"


@dataclass
class Alert:
    type: AlertType
    value: float
    threshold: float


def check_alerts(
    flow: FlowResult,
    oi_change: float,
    liq_stats: LiqStats,
    thresholds: dict[str, float],
) -> list[Alert]:
    alerts: list[Alert] = []

    # 大单流向异常
    whale_threshold = thresholds.get("whale_flow_usd", 10000000)
    if abs(flow.net) > whale_threshold:
        alerts.append(
            Alert(
                type=AlertType.WHALE_FLOW,
                value=flow.net,
                threshold=whale_threshold,
            )
        )

    # OI 变化异常
    oi_threshold = thresholds.get("oi_change_pct", 3)
    if abs(oi_change) > oi_threshold:
        alerts.append(
            Alert(
                type=AlertType.OI_CHANGE,
                value=oi_change,
                threshold=oi_threshold,
            )
        )

    # 爆仓异常
    liq_threshold = thresholds.get("liq_usd", 20000000)
    if liq_stats.total > liq_threshold:
        alerts.append(
            Alert(
                type=AlertType.LIQUIDATION,
                value=liq_stats.total,
                threshold=liq_threshold,
            )
        )

    return alerts


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
