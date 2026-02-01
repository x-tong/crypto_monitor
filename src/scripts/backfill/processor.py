"""aggTrades 数据处理器"""

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def calculate_monthly_p95_threshold(csv_path: Path) -> float:
    """计算单月 aggTrades 的 P95 大单阈值"""
    values = []

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            price = float(row["price"])
            quantity = float(row["quantity"])
            value_usd = price * quantity
            values.append(value_usd)

    if not values:
        return 100000.0  # 默认阈值

    values.sort()
    p95_index = int(len(values) * 0.95)
    return values[p95_index] if p95_index < len(values) else values[-1]


def process_agg_trades_to_flow(
    csv_path: Path,
    threshold: float,
) -> dict[int, float]:
    """
    处理 aggTrades CSV 为小时级净流向

    Args:
        csv_path: aggTrades CSV 文件路径
        threshold: 大单阈值 (USD)

    Returns:
        {timestamp_hour_ms: net_flow_usd}
    """
    hourly_flow: dict[int, float] = {}

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            price = float(row["price"])
            quantity = float(row["quantity"])
            value_usd = price * quantity

            # 过滤小单
            if value_usd < threshold:
                continue

            # is_buyer_maker=True 表示卖单成交 (maker 是买方，taker 是卖方)
            is_sell = row["is_buyer_maker"].lower() == "true"

            # 按小时聚合
            timestamp = int(row["transact_time"])
            hour_ts = (timestamp // 3600000) * 3600000  # 取整到小时

            if hour_ts not in hourly_flow:
                hourly_flow[hour_ts] = 0.0

            if is_sell:
                hourly_flow[hour_ts] -= value_usd
            else:
                hourly_flow[hour_ts] += value_usd

    return hourly_flow


def process_all_months(
    csv_files: list[Path],
    output_path: Path,
) -> None:
    """处理所有月份的 aggTrades，输出到单个文件"""
    all_flow: dict[int, float] = {}

    for csv_path in sorted(csv_files):
        logger.info(f"Processing {csv_path.name}...")

        # 计算该月的 P95 阈值
        threshold = calculate_monthly_p95_threshold(csv_path)
        logger.info(f"  P95 threshold: ${threshold:,.0f}")

        # 处理
        monthly_flow = process_agg_trades_to_flow(csv_path, threshold)
        all_flow.update(monthly_flow)

    # 输出
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("timestamp,value\n")
        for ts in sorted(all_flow.keys()):
            f.write(f"{ts},{all_flow[ts]}\n")

    logger.info(f"Saved flow data to {output_path}")
