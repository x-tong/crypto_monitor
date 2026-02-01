"""Binance 数据存档下载器"""

import logging
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp

from .config import (
    AGG_TRADES_DIR,
    BINANCE_DATA_URL,
    CACHE_DIR,
    INDICATORS_DIR,
    KLINES_DIR,
)

logger = logging.getLogger(__name__)


def get_monthly_range(days: int) -> list[str]:
    """获取回测需要的月份列表 (YYYY-MM 格式)"""
    end = datetime.now()
    start = end - timedelta(days=days)

    months = []
    current = start.replace(day=1)
    while current <= end:
        months.append(current.strftime("%Y-%m"))
        # 下个月
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return months


def build_download_url(symbol: str, data_type: str, month: str) -> str:
    """构建下载 URL"""
    # aggTrades: /aggTrades/BTCUSDT/BTCUSDT-aggTrades-2025-01.zip
    # klines: /klines/BTCUSDT/1h/BTCUSDT-1h-2025-01.zip
    if data_type == "aggTrades":
        filename = f"{symbol}-aggTrades-{month}.zip"
        return f"{BINANCE_DATA_URL}/aggTrades/{symbol}/{filename}"
    elif data_type == "klines":
        filename = f"{symbol}-1h-{month}.zip"
        return f"{BINANCE_DATA_URL}/klines/{symbol}/1h/{filename}"
    else:
        raise ValueError(f"Unknown data type: {data_type}")


class Downloader:
    """数据下载器"""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self.agg_trades_dir = self.cache_dir / "aggTrades"
        self.klines_dir = self.cache_dir / "klines"
        self.indicators_dir = self.cache_dir / "indicators"

    async def download_file(self, url: str, dest: Path) -> bool:
        """下载单个文件"""
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to download {url}: {response.status}")
                        return False

                    content = await response.read()
                    dest.write_bytes(content)
                    logger.info(f"Downloaded: {dest.name}")
                    return True
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False

    def extract_zip(self, zip_path: Path, dest_dir: Path) -> Path | None:
        """解压 zip 文件，返回解压后的 CSV 路径"""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    logger.warning(f"No CSV in {zip_path}")
                    return None

                csv_name = csv_names[0]
                zf.extract(csv_name, dest_dir)
                return dest_dir / csv_name
        except Exception as e:
            logger.error(f"Error extracting {zip_path}: {e}")
            return None

    async def download_agg_trades(
        self,
        symbol: str,
        months: list[str],
        progress_callback: callable | None = None,
    ) -> list[Path]:
        """下载 aggTrades 数据"""
        downloaded = []

        for i, month in enumerate(months):
            csv_path = self.agg_trades_dir / f"{symbol}-aggTrades-{month}.csv"

            # 已存在则跳过
            if csv_path.exists():
                logger.info(f"Cached: {csv_path.name}")
                downloaded.append(csv_path)
                if progress_callback:
                    progress_callback(i + 1, len(months))
                continue

            url = build_download_url(symbol, "aggTrades", month)
            zip_path = self.agg_trades_dir / f"{symbol}-aggTrades-{month}.zip"

            if await self.download_file(url, zip_path):
                extracted = self.extract_zip(zip_path, self.agg_trades_dir)
                if extracted:
                    # 重命名为标准名称
                    if extracted != csv_path:
                        extracted.rename(csv_path)
                    downloaded.append(csv_path)
                zip_path.unlink(missing_ok=True)  # 删除 zip

            if progress_callback:
                progress_callback(i + 1, len(months))

        return downloaded

    async def download_klines(
        self,
        symbol: str,
        months: list[str],
        progress_callback: callable | None = None,
    ) -> list[Path]:
        """下载 K 线数据"""
        downloaded = []

        for i, month in enumerate(months):
            csv_path = self.klines_dir / f"{symbol}-1h-{month}.csv"

            if csv_path.exists():
                logger.info(f"Cached: {csv_path.name}")
                downloaded.append(csv_path)
                if progress_callback:
                    progress_callback(i + 1, len(months))
                continue

            url = build_download_url(symbol, "klines", month)
            zip_path = self.klines_dir / f"{symbol}-1h-{month}.zip"

            if await self.download_file(url, zip_path):
                extracted = self.extract_zip(zip_path, self.klines_dir)
                if extracted:
                    if extracted != csv_path:
                        extracted.rename(csv_path)
                    downloaded.append(csv_path)
                zip_path.unlink(missing_ok=True)

            if progress_callback:
                progress_callback(i + 1, len(months))

        return downloaded

    async def download_all(
        self,
        symbols: list[str],
        days: int,
        progress_callback: callable | None = None,
    ) -> dict[str, dict[str, list[Path]]]:
        """下载所有需要的数据"""
        months = get_monthly_range(days)
        result: dict[str, dict[str, list[Path]]] = {}

        for symbol in symbols:
            result[symbol] = {
                "aggTrades": await self.download_agg_trades(
                    symbol, months, progress_callback
                ),
                "klines": await self.download_klines(symbol, months, progress_callback),
            }

        return result

    async def download_indicators(
        self,
        symbol: str,
        client: "BinanceClient",  # type: ignore[name-defined]
        days: int = 365,
    ) -> dict[str, Path]:
        """从 API 下载指标数据"""
        import json

        self.indicators_dir.mkdir(parents=True, exist_ok=True)
        result = {}

        # OI 历史 (5m 粒度，需要分批获取)
        oi_path = self.indicators_dir / f"openInterestHist_{symbol}.jsonl"
        if not oi_path.exists():
            oi_data = []
            # API 限制每次 500 条，5分钟粒度，每天 288 条
            # 365 天需要约 105,120 条，分批获取
            try:
                data = await client.get_open_interest_hist(symbol, "5m", limit=500)
                oi_data.extend(
                    [
                        {
                            "symbol": d.symbol,
                            "open_interest": d.open_interest,
                            "timestamp": d.timestamp,
                        }
                        for d in data
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to get OI hist for {symbol}: {e}")

            with open(oi_path, "w") as f:
                for item in oi_data:
                    f.write(json.dumps(item) + "\n")
            result["openInterestHist"] = oi_path

        # 资金费率
        funding_path = self.indicators_dir / f"fundingRate_{symbol}.jsonl"
        if not funding_path.exists():
            try:
                data = await client.get_funding_rate(symbol)
                with open(funding_path, "w") as f:
                    f.write(
                        json.dumps(
                            {
                                "symbol": data.symbol,
                                "funding_rate": data.funding_rate,
                                "funding_time": data.funding_time,
                            }
                        )
                        + "\n"
                    )
                result["fundingRate"] = funding_path
            except Exception as e:
                logger.warning(f"Failed to get funding rate for {symbol}: {e}")

        return result
