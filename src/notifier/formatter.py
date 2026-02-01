# src/notifier/formatter.py
from datetime import UTC, datetime
from typing import Any

from src.aggregator.percentile import get_level_emoji


def _format_usd(value: float) -> str:
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    elif abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    else:
        return f"${value:,.0f}"


def _format_usd_signed(value: float) -> str:
    sign = "+" if value >= 0 else ""
    if abs(value) >= 1_000_000_000:
        return f"{sign}${abs(value) / 1_000_000_000:.1f}B"
    elif abs(value) >= 1_000_000:
        return f"{sign}${abs(value) / 1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{sign}${abs(value) / 1_000:.1f}K"
    else:
        return f"{sign}${abs(value):,.0f}"


def _level(pct: float) -> str:
    return f"{get_level_emoji(pct)} P{int(pct)}"


def format_report(data: dict[str, Any]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    flow_binance = data.get("flow_binance", 0)

    price_dir = "↑" if data["price_change_1h"] > 0 else "↓"
    oi_dir = "↑" if data["oi_change_1h"] > 0 else "↓"
    funding_desc = "多头付费" if data["funding_rate"] > 0 else "空头付费"
    ls_desc = "散户偏多" if data["long_short_ratio"] > 1 else "散户偏空"

    # Pre-format values to avoid long lines
    flow_1h = f"{_format_usd_signed(data['flow_1h'])} {_level(data['flow_1h_pct'])}"
    flow_4h = f"{_format_usd_signed(data['flow_4h'])} {_level(data['flow_4h_pct'])}"
    flow_24h = f"{_format_usd_signed(data['flow_24h'])} {_level(data['flow_24h_pct'])}"
    oi_1h = f"{data['oi_change_1h']:+.1f}% {_level(data['oi_change_1h_pct'])}"
    oi_4h = f"{data['oi_change_4h']:+.1f}% {_level(data['oi_change_4h_pct'])}"
    liq_1h_long = _format_usd(data["liq_1h_long"])
    liq_1h_short = _format_usd(data["liq_1h_short"])
    liq_4h_long = _format_usd(data["liq_4h_long"])
    liq_4h_short = _format_usd(data["liq_4h_short"])
    liq_1h = f"{_format_usd(data['liq_1h_total'])} {_level(data['liq_1h_pct'])}"
    liq_4h = f"{_format_usd(data['liq_4h_total'])} {_level(data['liq_4h_pct'])}"

    return f"""📊 {data["symbol"]} 市场快照
⏰ {now}

💵 ${data["price"]:,.0f} ({data["price_change_1h"]:+.1f}% 1h / {data["price_change_24h"]:+.1f}% 24h)

━━━━━━━━━━━━━━━━━━━━
💰 主力资金 (大单净流向):
  1h: {flow_1h} | 4h: {flow_4h}
  24h: {flow_24h}
  Binance: {_format_usd_signed(flow_binance)}

━━━━━━━━━━━━━━━━━━━━
📈 持仓量 (OI): {_format_usd(data["oi_value"])}
  1h: {oi_1h} | 4h: {oi_4h}
  → 价格{price_dir} OI{oi_dir} = {data["oi_interpretation"]}

━━━━━━━━━━━━━━━━━━━━
💥 爆仓:
  1h: {liq_1h} (多{liq_1h_long} / 空{liq_1h_short})
  4h: {liq_4h} (多{liq_4h_long} / 空{liq_4h_short})

━━━━━━━━━━━━━━━━━━━━
📊 情绪指标:
  资金费率: {data["funding_rate"]:+.2f}% {_level(data["funding_rate_pct"])} ({funding_desc})
  多空比: {data["long_short_ratio"]:.2f} {_level(data["long_short_ratio_pct"])} ({ls_desc})
  合约溢价: {data["spot_perp_spread"]:+.2f}% {_level(data["spot_perp_spread_pct"])}"""


def format_price_alert(data: dict[str, Any]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    action = "突破" if data["type"] == "breakout" else "跌破"

    # Pre-format values
    flow_1h = f"{_format_usd_signed(data['flow_1h'])} {_level(data['flow_1h_pct'])}"
    oi_1h = f"{data['oi_change_1h']:+.1f}% {_level(data['oi_change_1h_pct'])}"
    liq_1h = f"{_format_usd(data['liq_1h_total'])} {_level(data['liq_1h_pct'])}"
    liq_1h_long = _format_usd(data["liq_1h_long"])
    liq_1h_short = _format_usd(data["liq_1h_short"])

    return f"""📍 {data["symbol"]} {action} {int(data["target_price"])}

💵 当前: ${data["current_price"]:,.0f} ({data["price_change_1h"]:+.1f}% 1h)

💰 主力资金 1h: {flow_1h}
📈 OI 变化 1h: {oi_1h}
💥 爆仓 1h: {liq_1h} (多{liq_1h_long} / 空{liq_1h_short})
📊 资金费率: {data["funding_rate"]:+.2f}% {_level(data["funding_rate_pct"])}

⏰ {now}"""


def format_whale_alert(data: dict[str, Any]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    direction = "净流入" if data["flow_1h"] > 0 else "净流出"

    return f"""⚠️ {data["symbol"]} 大单异常

1h {direction} {_format_usd(abs(data["flow_1h"]))} {_level(data["flow_1h_pct"])}
  Binance: {_format_usd_signed(data.get("flow_binance", 0))}

💵 ${data["price"]:,.0f} ({data["price_change_1h"]:+.1f}% 1h)
⏰ {now}"""


def _ratio_to_pct(ratio: float) -> int:
    """将比率转换为多头百分比: 2.0 -> 67%"""
    if ratio <= 0:
        return 50
    return int(ratio / (ratio + 1) * 100)


def _change_desc(change: float, is_long_ratio: bool = True) -> str:
    """生成变化描述"""
    if abs(change) < 0.01:
        return "持平"
    if is_long_ratio:
        return "加多" if change > 0 else "减多"
    return "买方增强" if change > 0 else "卖方增强"


def _oi_interpretation(oi_change: float, price_change: float) -> str:
    """OI + 价格组合解读"""
    if abs(oi_change) < 0.5:
        return "持仓稳定"
    oi_up = oi_change > 0
    price_up = price_change >= 0
    if oi_up and price_up:
        return "新多入场"
    elif oi_up and not price_up:
        return "新空入场"
    elif not oi_up and price_up:
        return "空头平仓"
    else:
        return "多头平仓"


def format_insight_report(data: dict[str, Any]) -> str:
    """生成市场洞察报告"""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # 转换比率为百分比
    top_long_pct = _ratio_to_pct(data["top_position_ratio"])
    top_short_pct = 100 - top_long_pct
    global_long_pct = _ratio_to_pct(data["global_account_ratio"])
    global_short_pct = 100 - global_long_pct
    taker_buy_pct = _ratio_to_pct(data["taker_ratio"])
    taker_sell_pct = 100 - taker_buy_pct

    # 变化方向和描述
    top_dir = "↑" if data["top_position_change"] > 0 else "↓"
    top_change_pct = abs(data["top_position_change"]) / max(data["top_position_ratio"], 0.01) * 100
    top_desc = _change_desc(data["top_position_change"])

    global_dir = "↑" if data["global_account_change"] > 0 else "↓"
    global_change_pct = (
        abs(data["global_account_change"]) / max(data["global_account_ratio"], 0.01) * 100
    )
    global_desc = _change_desc(data["global_account_change"])

    # 大户散户一致性判断
    both_long = top_long_pct > 50 and global_long_pct > 50
    both_short = top_long_pct < 50 and global_long_pct < 50
    if both_long:
        consensus = "大户散户一致看多"
    elif both_short:
        consensus = "大户散户一致看空"
    else:
        consensus = "大户散户存在分歧"

    # 资金流向
    flow_1h = _format_usd_signed(data["flow_1h"])
    flow_binance = _format_usd_signed(data["flow_binance"])

    # Taker 描述
    if taker_buy_pct > 55:
        taker_desc = "买方主导"
    elif taker_buy_pct < 45:
        taker_desc = "卖方主导"
    else:
        taker_desc = "买卖均衡"

    # OI 解读
    oi_interp = _oi_interpretation(data["oi_change_1h"], data["price_change_1h"])

    # 爆仓
    liq_long_pct = int(data["liq_long_ratio"] * 100)
    liq_short_pct = 100 - liq_long_pct
    if data["liq_long_ratio"] > 0.65:
        liq_desc = "多头承压"
    elif data["liq_long_ratio"] < 0.35:
        liq_desc = "空头承压"
    else:
        liq_desc = "多空均衡"

    # 资金费率描述
    if data["funding_rate"] > 0.01:
        funding_desc = "多头付费，情绪偏多"
    elif data["funding_rate"] < -0.01:
        funding_desc = "空头付费，情绪偏空"
    else:
        funding_desc = "费率中性"

    # 收集异常维度 (≥P90)
    anomalies: list[str] = []
    if data["top_position_pct"] >= 90:
        anomalies.append(f"大户持仓 P{int(data['top_position_pct'])}")
    if data["global_account_pct"] >= 90:
        anomalies.append(f"散户持仓 P{int(data['global_account_pct'])}")
    if data["flow_1h_pct"] >= 90:
        anomalies.append(f"主力资金 {flow_1h} P{int(data['flow_1h_pct'])}")
    if data["oi_change_1h_pct"] >= 90:
        anomalies.append(f"OI变化 {data['oi_change_1h']:+.1f}% P{int(data['oi_change_1h_pct'])}")
    if data["funding_rate_pct"] >= 90:
        anomalies.append(f"资金费率 P{int(data['funding_rate_pct'])}")

    if anomalies:
        anomaly_section = "⚠️ 异常维度 (≥P90)\n" + "\n".join(f"  🔴 {a}" for a in anomalies)
    else:
        anomaly_section = "✅ 各维度正常，无异常"

    # 构建报告
    return f"""📊 {data["symbol"]} 市场洞察
━━━━━━━━━━━━━━━━━━━━
💵 ${data["price"]:,.0f} ({data["price_change_1h"]:+.1f}% vs 1h前)

━━━━━━━━━━━━━━━━━━━━
🎯 多空对比 [5m更新]

  大户: {top_long_pct}% 多 / {top_short_pct}% 空 {_level(data["top_position_pct"])}
        {top_dir}{top_change_pct:.0f}% vs 1h前 ({top_desc})

  散户: {global_long_pct}% 多 / {global_short_pct}% 空 {_level(data["global_account_pct"])}
        {global_dir}{global_change_pct:.0f}% vs 1h前 ({global_desc})

  → {consensus}

━━━━━━━━━━━━━━━━━━━━
💰 资金动向 [实时]

  主力净流向 (1h): {flow_1h} {_level(data["flow_1h_pct"])}
    Binance: {flow_binance}

  Taker: {taker_buy_pct}% 买 / {taker_sell_pct}% 卖 {_level(data["taker_ratio_pct"])}
         {taker_desc}

━━━━━━━━━━━━━━━━━━━━
📈 持仓 & 爆仓 [实时]

  OI: {_format_usd(data["oi_value"])}
      {data["oi_change_1h"]:+.1f}% vs 1h前 {_level(data["oi_change_1h_pct"])}
      → {oi_interp}

  爆仓 (1h): {_format_usd(data["liq_1h_total"])}
      多 {liq_long_pct}% / 空 {liq_short_pct}%
      → {liq_desc}

━━━━━━━━━━━━━━━━━━━━
📊 情绪指标

  资金费率: {data["funding_rate"]:+.3f}% {_level(data["funding_rate_pct"])}
            {funding_desc}

  合约溢价: {data["spot_perp_spread"]:+.2f}% {_level(data["spot_perp_spread_pct"])}

━━━━━━━━━━━━━━━━━━━━
{anomaly_section}

⏰ {now}"""


def _ratio_to_long_pct(ratio: float) -> float:
    """将多空比转换为多头占比百分比"""
    if ratio <= 0:
        return 50.0
    return ratio / (1 + ratio) * 100


def _format_dimension_detail(name: str, pct: float, data: dict[str, Any]) -> list[str]:
    """格式化单个维度的详细信息"""
    lines: list[str] = []

    if name in ("散户持仓", "大户持仓", "多空比"):
        # 显示大户 vs 散户对比
        top_ratio = data.get("top_position_ratio", 1.0)
        global_ratio = data.get("global_account_ratio", 1.0)
        top_pct = data.get("top_position_pct", 50)
        global_pct = data.get("global_account_pct", 50)

        top_long = _ratio_to_long_pct(top_ratio)
        global_long = _ratio_to_long_pct(global_ratio)

        lines.append("🎯 持仓多空比极端")
        lines.append(
            f"  散户: {global_long:.0f}% 多 / {100 - global_long:.0f}% 空 "
            f"{get_level_emoji(global_pct)} P{int(global_pct)}"
        )
        lines.append(
            f"  大户: {top_long:.0f}% 多 / {100 - top_long:.0f}% 空 "
            f"{get_level_emoji(top_pct)} P{int(top_pct)}"
        )

        # 解读
        if global_long > top_long + 5:
            lines.append("  → 散户比大户更激进做多")
        elif top_long > global_long + 5:
            lines.append("  → 大户比散户更激进做多")
        else:
            lines.append("  → 大户散户一致看多")

    elif name == "主力资金":
        flow_net = data.get("flow_net", 0)
        flow_str = _format_usd_signed(flow_net)
        direction = "流入" if flow_net > 0 else "流出"
        lines.append(f"💰 主力资金 1h 净{direction}")
        lines.append(f"  {flow_str} 🔴 P{int(pct)}")

    elif name == "OI变化":
        oi_change = data.get("oi_change", 0)
        direction = "增加" if oi_change > 0 else "减少"
        lines.append(f"📈 持仓量 1h {direction}")
        lines.append(f"  {oi_change:+.2f}% 🔴 P{int(pct)}")

    elif name == "爆仓":
        liq_total = data.get("liq_total", 0)
        lines.append("💥 爆仓异常")
        lines.append(f"  1h 总爆仓: {_format_usd(liq_total)} 🔴 P{int(pct)}")

    elif name == "资金费率":
        funding = data.get("funding_rate", 0)
        direction = "多头付费" if funding > 0 else "空头付费"
        lines.append("📊 资金费率极端")
        lines.append(f"  {funding:.4%} ({direction}) 🔴 P{int(pct)}")

    else:
        # 其他维度
        lines.append(f"• {name}: 🔴 P{int(pct)}")

    return lines


def format_observe_alert(data: dict[str, Any]) -> str:
    """格式化观察提醒（详细版）"""
    lines = [
        f"📢 {data['symbol']} 观察提醒",
        "",
    ]

    # 只显示第一个（最重要的）维度的详细信息
    dimensions = data.get("dimensions", [])
    if dimensions:
        name, pct = dimensions[0]
        lines.extend(_format_dimension_detail(name, pct, data))

    lines.extend(
        [
            "",
            f"💵 ${data['price']:,.0f} ({data['price_change_1h']:+.1f}% 1h)",
            f"⏰ {data['timestamp']}",
            "",
            "ℹ️ P90+ = 历史90%的时候都比现在低",
        ]
    )

    return "\n".join(lines)


def format_important_alert(data: dict[str, Any]) -> str:
    """格式化重要提醒（多维度共振）"""
    dimensions = data.get("dimensions", [])
    dim_count = len(dimensions)

    lines = [
        f"🚨 {data['symbol']} 重要提醒",
        f"⚠️ {dim_count} 个维度同时处于极端值",
        "",
    ]

    # 显示所有维度的详细信息
    shown_position = False
    for name, pct in dimensions:
        # 持仓相关维度只显示一次（合并大户/散户/多空比）
        if name in ("散户持仓", "大户持仓", "多空比"):
            if not shown_position:
                lines.extend(_format_dimension_detail(name, pct, data))
                lines.append("")
                shown_position = True
        else:
            lines.extend(_format_dimension_detail(name, pct, data))
            lines.append("")

    lines.extend(
        [
            f"💵 ${data['price']:,.0f} ({data['price_change_1h']:+.1f}% 1h)",
            f"⏰ {data['timestamp']}",
        ]
    )

    return "\n".join(lines)
