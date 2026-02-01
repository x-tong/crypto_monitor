# src/scripts/backfill_events.py
"""
历史极端事件回测脚本

用法:
    uv run python -m src.scripts.backfill_events --days 365
    uv run python -m src.scripts.backfill_events --days 365 --symbol BTC
"""
import argparse
import asyncio
import logging
from typing import Sequence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="回测历史极端事件")
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="回测天数 (默认: 365)",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="只回测指定 symbol (默认: 全部)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要插入的事件，不实际写入",
    )
    return parser.parse_args(args)


def calculate_historical_percentile(
    history: list[float],
    current_idx: int,
    value: float,
    window_days: int,
) -> float | None:
    """
    计算历史某一时刻的滚动窗口百分位

    Args:
        history: 完整历史数据列表
        current_idx: 当前时刻在 history 中的索引
        value: 当前值
        window_days: 窗口大小（天）

    Returns:
        百分位，数据不足时返回 None
    """
    start_idx = max(0, current_idx - window_days + 1)
    window_data = history[start_idx : current_idx + 1]

    if len(window_data) < window_days:
        return None

    count_below = sum(1 for h in window_data if h < abs(value))
    return count_below / len(window_data) * 100


async def main() -> None:
    args = parse_args()
    logger.info(f"Starting backfill for {args.days} days")

    # TODO: 实现完整的回测逻辑
    # 1. 下载历史数据
    # 2. 计算每个时间点的百分位
    # 3. 识别 P90+ 事件
    # 4. 插入 extreme_events 表
    # 5. 回填后续价格

    logger.info("Backfill complete")


if __name__ == "__main__":
    asyncio.run(main())
