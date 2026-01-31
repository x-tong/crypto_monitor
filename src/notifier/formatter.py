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

    # 判断交易所一致性
    flow_binance = data.get("flow_binance", 0)
    flow_okx = data.get("flow_okx", 0)
    consistency = "✓一致" if (flow_binance >= 0) == (flow_okx >= 0) else "⚠️分歧"

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
  Binance: {_format_usd_signed(flow_binance)} | OKX: {_format_usd_signed(flow_okx)} {consistency}

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
  OKX: {_format_usd_signed(data.get("flow_okx", 0))}

💵 ${data["price"]:,.0f} ({data["price_change_1h"]:+.1f}% 1h)
⏰ {now}"""
