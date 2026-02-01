"""价格回填器"""

import csv
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 回填时间点（毫秒）
BACKFILL_OFFSETS = {
    "price_4h": 4 * 3600 * 1000,
    "price_12h": 12 * 3600 * 1000,
    "price_24h": 24 * 3600 * 1000,
    "price_48h": 48 * 3600 * 1000,
}


def load_klines(csv_files: list[Path]) -> dict[int, float]:
    """
    加载 K 线数据

    Returns:
        {open_time_ms: close_price}
    """
    klines = {}

    for csv_path in sorted(csv_files):
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                open_time = int(row["open_time"])
                close_price = float(row["close"])
                klines[open_time] = close_price

    return klines


def backfill_prices(
    event: dict[str, Any],
    klines: dict[int, float],
) -> dict[str, Any]:
    """
    为单个事件回填后续价格

    Args:
        event: 极端事件字典
        klines: {timestamp: close_price}

    Returns:
        添加了价格字段的事件
    """
    triggered_at = event["triggered_at"]

    # 触发时价格
    event["price_at_trigger"] = klines.get(triggered_at)

    # 后续价格
    for field, offset in BACKFILL_OFFSETS.items():
        target_ts = triggered_at + offset
        event[field] = klines.get(target_ts)

    return event


def backfill_all_events(
    events: list[dict[str, Any]],
    klines: dict[int, float],
) -> list[dict[str, Any]]:
    """为所有事件回填价格"""
    backfilled = []
    missing_count = 0

    for event in events:
        result = backfill_prices(event, klines)
        if result["price_at_trigger"] is None:
            missing_count += 1
        backfilled.append(result)

    if missing_count > 0:
        logger.warning(f"{missing_count} events missing price_at_trigger")

    return backfilled
