# src/aggregator/insight.py
from src.aggregator.percentile import calculate_percentile


def calculate_divergence(
    top_ratio: float,
    global_ratio: float,
    history: list[float],
    mild_pct: float = 75,
    strong_pct: float = 90,
) -> dict:
    """
    计算大户与散户的分歧程度

    Args:
        top_ratio: 大户持仓多空比
        global_ratio: 散户账户多空比
        history: 历史分歧度列表
        mild_pct: 轻度分歧百分位阈值
        strong_pct: 显著分歧百分位阈值

    Returns:
        divergence: 分歧度 (正=大户更看多, 负=大户更看空)
        percentile: 当前分歧在历史中的百分位
        level: 分歧级别 (none/mild/strong)
    """
    divergence = top_ratio - global_ratio
    percentile = calculate_percentile(abs(divergence), history)

    if percentile < mild_pct:
        level = "none"
    elif percentile < strong_pct:
        level = "mild"
    else:
        level = "strong"

    return {
        "divergence": divergence,
        "percentile": percentile,
        "level": level,
    }


def calculate_change(current: float, previous: float) -> dict:
    """计算指标变化"""
    diff = current - previous
    if diff > 0.001:
        direction = "↑"
    elif diff < -0.001:
        direction = "↓"
    else:
        direction = "→"

    return {"diff": round(diff, 4), "direction": direction}


def generate_summary(data: dict) -> str:
    """
    生成一句话市场总结（规则版）

    预留接口供未来 AI 替换
    """
    parts = []

    # 大户动向
    top_change = data.get("top_ratio_change", 0)
    if top_change > 0.05:
        parts.append("大户加多")
    elif top_change < -0.05:
        parts.append("大户减多")

    # 分歧情况
    div_level = data.get("divergence_level", "none")
    div = data.get("divergence", 0)
    if div_level == "strong":
        if div > 0:
            parts.append("与散户分歧（大户更看多）")
        else:
            parts.append("与散户分歧（大户更看空）")
    elif div_level == "mild":
        parts.append("大户散户轻度分歧")

    # 资金流向
    flow = data.get("flow_1h", 0)
    if flow > 1_000_000:
        parts.append("资金流入")
    elif flow < -1_000_000:
        parts.append("资金流出")

    # 爆仓压力
    liq_long_ratio = data.get("liq_long_ratio", 0.5)
    if liq_long_ratio > 0.65:
        parts.append("多头承压")
    elif liq_long_ratio < 0.35:
        parts.append("空头承压")

    return "，".join(parts) if parts else "市场平稳"
