# src/alert/insight_trigger.py
from dataclasses import dataclass
from typing import Any


@dataclass
class InsightAlert:
    type: str  # divergence_spike, whale_flip, flow_reversal, taker_extreme
    message: str


def check_insight_alerts(
    current: dict[str, Any],
    previous: dict[str, Any],
    flow_threshold: float = 5_000_000,
) -> list[InsightAlert]:
    """
    检测市场异动

    Args:
        current: 当前市场指标
        previous: 上一周期市场指标
        flow_threshold: 资金反转阈值

    Returns:
        触发的异动提醒列表
    """
    alerts = []

    # 1. 大户散户分歧突变
    if current["divergence_level"] == "strong" and previous["divergence_level"] != "strong":
        alerts.append(InsightAlert(type="divergence_spike", message="大户散户分歧加剧"))

    # 2. 大户方向反转 (多空比跨越 1.0)
    curr_top = current["top_ratio"]
    prev_top = previous["top_ratio"]
    if (curr_top > 1 and prev_top < 1) or (curr_top < 1 and prev_top > 1):
        direction = "转多" if curr_top > 1 else "转空"
        alerts.append(InsightAlert(type="whale_flip", message=f"大户方向反转：{direction}"))

    # 3. 资金流向反转
    curr_flow = current["flow_1h"]
    prev_flow = previous["flow_1h"]
    if (curr_flow > 0 and prev_flow < 0) or (curr_flow < 0 and prev_flow > 0):
        if abs(curr_flow) > flow_threshold:
            direction = "转为流入" if curr_flow > 0 else "转为流出"
            alerts.append(InsightAlert(type="flow_reversal", message=f"资金流向反转：{direction}"))

    # 4. 主动买卖比极端值
    if current["taker_ratio_pct"] > 90:
        direction = "主动买入极端" if current.get("taker_ratio", 1) > 1 else "主动卖出极端"
        alerts.append(InsightAlert(type="taker_extreme", message=direction))

    return alerts
