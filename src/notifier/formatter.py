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


def format_insight_report(data: dict[str, Any]) -> str:
    """生成市场洞察报告"""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # 大户 vs 散户
    top_dir = "↑" if data["top_position_change"] > 0 else "↓"
    global_dir = "↑" if data["global_account_change"] > 0 else "↓"

    # 分歧描述
    if data["divergence_level"] == "strong":
        div_desc = "大户更看多" if data["divergence"] > 0 else "大户更看空"
        div_line = (
            f"  ⚠️ 分歧度: {data['divergence']:.2f} 🔴 P{int(data['divergence_pct'])} ({div_desc})"
        )
    elif data["divergence_level"] == "mild":
        div_desc = "大户偏多" if data["divergence"] > 0 else "大户偏空"
        div_line = (
            f"  分歧度: {data['divergence']:.2f} 🟡 P{int(data['divergence_pct'])} ({div_desc})"
        )
    else:
        div_line = f"  分歧度: {data['divergence']:.2f} 🟢 P{int(data['divergence_pct'])} (一致)"

    # 主动买卖
    taker_dir = "↑" if data["taker_ratio_change"] > 0 else "↓"

    # 资金流向
    flow_1h = _format_usd_signed(data["flow_1h"])
    flow_binance = _format_usd_signed(data["flow_binance"])

    # 爆仓压力
    liq_long_pct = int(data["liq_long_ratio"] * 100)
    liq_short_pct = 100 - liq_long_pct
    if data["liq_long_ratio"] > 0.65:
        liq_pressure = "← 多头承压"
    elif data["liq_long_ratio"] < 0.35:
        liq_pressure = "← 空头承压"
    else:
        liq_pressure = ""

    # Pre-format for readability
    top_pos = (
        f"{data['top_position_ratio']:.2f} "
        f"({top_dir}{abs(data['top_position_change']):.2f} vs 1h) "
        f"{_level(data['top_position_pct'])}"
    )
    global_acc = (
        f"{data['global_account_ratio']:.2f} "
        f"({global_dir}{abs(data['global_account_change']):.2f} vs 1h) "
        f"{_level(data['global_account_pct'])}"
    )
    taker = (
        f"{data['taker_ratio']:.2f} "
        f"({taker_dir}{abs(data['taker_ratio_change']):.2f} vs 1h) "
        f"{_level(data['taker_ratio_pct'])}"
    )
    flow_line = f"{flow_1h} {_level(data['flow_1h_pct'])}"
    oi_line = (
        f"{_format_usd(data['oi_value'])} "
        f"({data['oi_change_1h']:+.1f}% vs 1h) "
        f"{_level(data['oi_change_1h_pct'])}"
    )
    liq_line = (
        f"{_format_usd(data['liq_1h_total'])} "
        f"(多{liq_long_pct}% / 空{liq_short_pct}%) {liq_pressure}"
    )

    return f"""📊 {data["symbol"]} 市场洞察
⏰ {now}

🎯 {data["summary"]}

━━━━━━━━━━━━━━━━━━━━
💵 价格: ${data["price"]:,.0f} ({data["price_change_1h"]:+.1f}% 1h)

━━━━━━━━━━━━━━━━━━━━
🐋 大户 vs 散户
  大户持仓比: {top_pos}
  散户账户比: {global_acc}
{div_line}

━━━━━━━━━━━━━━━━━━━━
💰 资金动向
  主动买卖比: {taker}
  大单净流向: {flow_line}
    Binance: {flow_binance}

━━━━━━━━━━━━━━━━━━━━
📈 持仓 & 爆仓
  OI: {oi_line}
  爆仓 1h: {liq_line}

━━━━━━━━━━━━━━━━━━━━
📊 情绪指标
  资金费率: {data["funding_rate"]:+.3f}% {_level(data["funding_rate_pct"])}
  合约溢价: {data["spot_perp_spread"]:+.2f}% {_level(data["spot_perp_spread_pct"])}"""
