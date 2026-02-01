"""
历史极端事件回测脚本

用法:
    uv run python -m src.scripts.backfill_events --days 365
    uv run python -m src.scripts.backfill_events --days 365 --symbol BTC
    uv run python -m src.scripts.backfill_events --skip-download
    uv run python -m src.scripts.backfill_events --download-only
"""

import argparse
import asyncio
import logging
from collections.abc import Sequence

from src.scripts.backfill.config import (
    CACHE_DIR,
    PROCESSED_DIR,
)
from src.scripts.backfill.detector import detect_all_windows
from src.scripts.backfill.downloader import Downloader
from src.scripts.backfill.price_backfiller import backfill_prices, load_klines
from src.scripts.backfill.processor import process_all_months
from src.storage.database import Database
from src.storage.models import ExtremeEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
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
        "--skip-download",
        action="store_true",
        help="跳过下载，使用已有缓存",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="只下载数据，不处理",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="清理缓存目录",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要插入的事件，不实际写入",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/monitor.db",
        help="数据库路径",
    )
    return parser.parse_args(args)


def load_processed_data(symbol: str, dimension: str) -> list[tuple[int, float]]:
    """加载处理后的数据"""
    import csv

    file_path = PROCESSED_DIR / f"{dimension}_{symbol}.csv"
    if not file_path.exists():
        return []

    data = []
    with open(file_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append((int(row["timestamp"]), float(row["value"])))
    return data


async def run_download(downloader: Downloader, symbols: list[str], days: int) -> None:
    """执行下载步骤"""
    logger.info("[1/5] 下载数据...")

    for symbol in symbols:
        binance_symbol = f"{symbol}USDT"
        logger.info(f"  下载 {binance_symbol}...")
        await downloader.download_all([binance_symbol], days)

    logger.info("  下载完成 ✓")


async def run_process(symbols: list[str]) -> None:
    """执行处理步骤"""
    logger.info("[2/5] 处理 aggTrades → 资金流向...")

    for symbol in symbols:
        binance_symbol = f"{symbol}USDT"
        csv_files = sorted(CACHE_DIR.glob(f"aggTrades/{binance_symbol}-aggTrades-*.csv"))

        if not csv_files:
            logger.warning(f"  {symbol}: 无 aggTrades 数据")
            continue

        output_path = PROCESSED_DIR / f"flow_1h_{binance_symbol}.csv"
        process_all_months(csv_files, output_path)
        logger.info(f"  {symbol}: 处理完成 ✓")


async def run_detect(symbols: list[str]) -> list[dict]:
    """执行检测步骤"""
    logger.info("[3/5] 计算百分位...")
    logger.info("[4/5] 识别极端事件...")

    all_events = []

    for symbol in symbols:
        binance_symbol = f"{symbol}USDT"

        for dimension in ["flow_1h"]:  # 目前只实现资金流向
            data = load_processed_data(binance_symbol, dimension)
            if not data:
                logger.warning(f"  {symbol}/{dimension}: 无数据")
                continue

            logger.info(f"  {symbol}/{dimension}: {len(data)} 数据点")
            events = detect_all_windows(data, dimension, symbol)
            all_events.extend(events)

    logger.info(f"  发现 {len(all_events)} 个事件")
    return all_events


async def run_backfill(
    events: list[dict],
    symbols: list[str],
) -> list[dict]:
    """执行价格回填步骤"""
    logger.info("[5/5] 回填后续价格...")

    # 加载所有 K 线
    all_klines: dict[str, dict[int, float]] = {}
    for symbol in symbols:
        binance_symbol = f"{symbol}USDT"
        csv_files = sorted(CACHE_DIR.glob(f"klines/{binance_symbol}-1h-*.csv"))
        klines = load_klines(csv_files)
        all_klines[symbol] = klines
        logger.info(f"  {symbol}: 加载 {len(klines)} K 线")

    # 回填价格
    for event in events:
        symbol = event["symbol"]
        if symbol in all_klines:
            backfill_prices(event, all_klines[symbol])

    return events


async def save_events(events: list[dict], db_path: str, dry_run: bool = False) -> None:
    """保存事件到数据库"""
    if dry_run:
        logger.info(f"[DRY RUN] 将插入 {len(events)} 个事件")
        for e in events[:5]:
            logger.info(
                f"  {e['symbol']} {e['dimension']} {e['window_days']}d: P{e['percentile']:.1f}"
            )
        if len(events) > 5:
            logger.info(f"  ... 还有 {len(events) - 5} 个")
        return

    db = Database(db_path)
    await db.init()

    count = 0
    for e in events:
        event = ExtremeEvent(
            id=None,
            symbol=e["symbol"],
            dimension=e["dimension"],
            window_days=e["window_days"],
            triggered_at=e["triggered_at"],
            value=e["value"],
            percentile=e["percentile"],
            price_at_trigger=e.get("price_at_trigger"),
            price_4h=e.get("price_4h"),
            price_12h=e.get("price_12h"),
            price_24h=e.get("price_24h"),
            price_48h=e.get("price_48h"),
        )
        await db.insert_extreme_event(event)
        count += 1

    await db.close()
    logger.info(f"  已保存 {count} 个事件到数据库")


async def main() -> None:
    args = parse_args()

    # 清理缓存
    if args.clean_cache:
        import shutil

        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            logger.info(f"已清理缓存: {CACHE_DIR}")
        return

    # 确定要处理的 symbol
    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = ["BTC", "ETH"]

    logger.info(f"开始回测: {args.days} 天, symbols={symbols}")

    downloader = Downloader()

    # Step 1: 下载
    if not args.skip_download:
        await run_download(downloader, symbols, args.days)

    if args.download_only:
        logger.info("下载完成，跳过处理")
        return

    # Step 2: 处理
    await run_process(symbols)

    # Step 3-4: 检测
    events = await run_detect(symbols)

    if not events:
        logger.info("未发现极端事件")
        return

    # Step 5: 回填
    events = await run_backfill(events, symbols)

    # 保存
    await save_events(events, args.db_path, args.dry_run)

    logger.info("回测完成!")


if __name__ == "__main__":
    asyncio.run(main())
