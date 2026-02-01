# 回测脚本完善 - 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完善历史极端事件回测脚本，从 Binance 数据存档下载 1 年历史数据，计算百分位并识别 P90+ 极端事件。

**Architecture:** 分层模块设计 - downloader 下载原始数据，processor 处理成标准格式，detector 识别极端事件写入数据库，backfiller 回填后续价格。使用本地文件缓存支持断点续传。

**Tech Stack:** Python 3.14, aiohttp, aiofiles, pandas (数据处理), gzip

---

## Task 1: 创建 backfill 模块结构

**Files:**
- Create: `src/scripts/backfill/__init__.py`
- Create: `src/scripts/backfill/config.py`

**Step 1: 创建目录和 __init__.py**

```python
# src/scripts/backfill/__init__.py
"""历史极端事件回测模块"""
```

**Step 2: 创建配置文件**

```python
# src/scripts/backfill/config.py
"""回测配置常量"""

from pathlib import Path

# 缓存目录
CACHE_DIR = Path("data/backfill_cache")
AGG_TRADES_DIR = CACHE_DIR / "aggTrades"
KLINES_DIR = CACHE_DIR / "klines"
INDICATORS_DIR = CACHE_DIR / "indicators"
PROCESSED_DIR = CACHE_DIR / "processed"

# Binance 数据存档 URL
BINANCE_DATA_URL = "https://data.binance.vision/data/futures/um/monthly"

# 支持的交易对
SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# 维度定义
DIMENSIONS = [
    "flow_1h",
    "oi_change_1h",
    "funding_rate",
    "top_position_ratio",
    "global_account_ratio",
    "taker_ratio",
]

# 百分位窗口（小时）
WINDOWS = {
    7: 7 * 24,    # 168 小时
    30: 30 * 24,  # 720 小时
    90: 90 * 24,  # 2160 小时
}

# 极端事件阈值
EXTREME_THRESHOLD = 90

# 冷却期（小时）
COOLDOWN_HOURS = 1
```

**Step 3: 运行验证**

Run: `uv run python -c "from src.scripts.backfill.config import CACHE_DIR; print(CACHE_DIR)"`
Expected: `data/backfill_cache`

**Step 4: Commit**

```bash
git add src/scripts/backfill/
git commit -m "feat: 创建 backfill 模块结构和配置"
```

---

## Task 2: 实现数据存档下载器

**Files:**
- Create: `src/scripts/backfill/downloader.py`
- Create: `tests/scripts/backfill/__init__.py`
- Create: `tests/scripts/backfill/test_downloader.py`

**Step 1: 写失败的测试**

```python
# tests/scripts/backfill/test_downloader.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path


def test_get_monthly_range():
    from src.scripts.backfill.downloader import get_monthly_range

    # 365 天前到现在
    months = get_monthly_range(365)
    assert len(months) >= 12
    assert all(len(m) == 7 for m in months)  # YYYY-MM 格式


def test_build_download_url():
    from src.scripts.backfill.downloader import build_download_url

    url = build_download_url("BTCUSDT", "aggTrades", "2025-01")
    assert "data.binance.vision" in url
    assert "BTCUSDT" in url
    assert "aggTrades" in url
    assert "2025-01" in url


async def test_download_file_creates_cache_dir(tmp_path):
    from src.scripts.backfill.downloader import Downloader

    downloader = Downloader(cache_dir=tmp_path)

    # Mock HTTP response
    with patch("aiohttp.ClientSession") as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"test data")
        mock_session.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        await downloader.download_file(
            "https://example.com/test.zip",
            tmp_path / "test.zip"
        )

    assert (tmp_path / "test.zip").exists()
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/scripts/backfill/test_downloader.py -v`
Expected: FAIL with "No module named 'src.scripts.backfill.downloader'"

**Step 3: 实现下载器**

```python
# src/scripts/backfill/downloader.py
"""Binance 数据存档下载器"""

import asyncio
import gzip
import logging
import shutil
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
    SYMBOLS,
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
        self, symbol: str, months: list[str], progress_callback: callable | None = None
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
        self, symbol: str, months: list[str], progress_callback: callable | None = None
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
                "aggTrades": await self.download_agg_trades(symbol, months, progress_callback),
                "klines": await self.download_klines(symbol, months, progress_callback),
            }

        return result
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/scripts/backfill/test_downloader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/scripts/backfill/downloader.py tests/scripts/backfill/
git commit -m "feat: 实现 Binance 数据存档下载器"
```

---

## Task 3: 实现 API 指标下载

**Files:**
- Modify: `src/scripts/backfill/downloader.py`
- Modify: `tests/scripts/backfill/test_downloader.py`

**Step 1: 写失败的测试**

在 `tests/scripts/backfill/test_downloader.py` 末尾添加：

```python
async def test_download_indicators_from_api(tmp_path):
    from src.scripts.backfill.downloader import Downloader
    from unittest.mock import AsyncMock, MagicMock

    downloader = Downloader(cache_dir=tmp_path)

    # Mock BinanceClient
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    # Mock API 响应
    mock_oi = MagicMock()
    mock_oi.symbol = "BTCUSDT"
    mock_oi.open_interest = 50000.0
    mock_oi.timestamp = 1704067200000
    mock_client.get_open_interest_hist = AsyncMock(return_value=[mock_oi])

    mock_funding = MagicMock()
    mock_funding.symbol = "BTCUSDT"
    mock_funding.funding_rate = 0.0001
    mock_funding.funding_time = 1704067200000
    mock_client.get_funding_rate = AsyncMock(return_value=mock_funding)

    await downloader.download_indicators("BTCUSDT", mock_client, days=7)

    # 验证文件创建
    oi_file = tmp_path / "indicators" / "openInterestHist_BTCUSDT.jsonl"
    assert oi_file.exists()
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/scripts/backfill/test_downloader.py::test_download_indicators_from_api -v`
Expected: FAIL with "Downloader object has no attribute 'download_indicators'"

**Step 3: 在 Downloader 类中添加 API 下载方法**

在 `src/scripts/backfill/downloader.py` 的 `Downloader` 类末尾添加：

```python
    async def download_indicators(
        self,
        symbol: str,
        client: "BinanceClient",
        days: int = 365,
    ) -> dict[str, Path]:
        """从 API 下载指标数据"""
        import json
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from src.client.binance import BinanceClient

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
                oi_data.extend([
                    {"symbol": d.symbol, "open_interest": d.open_interest, "timestamp": d.timestamp}
                    for d in data
                ])
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
                    f.write(json.dumps({
                        "symbol": data.symbol,
                        "funding_rate": data.funding_rate,
                        "funding_time": data.funding_time,
                    }) + "\n")
                result["fundingRate"] = funding_path
            except Exception as e:
                logger.warning(f"Failed to get funding rate for {symbol}: {e}")

        return result
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/scripts/backfill/test_downloader.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/scripts/backfill/downloader.py tests/scripts/backfill/test_downloader.py
git commit -m "feat: 添加 API 指标下载功能"
```

---

## Task 4: 实现 aggTrades 处理器

**Files:**
- Create: `src/scripts/backfill/processor.py`
- Create: `tests/scripts/backfill/test_processor.py`

**Step 1: 写失败的测试**

```python
# tests/scripts/backfill/test_processor.py
import pytest
from pathlib import Path


def test_calculate_monthly_p95_threshold(tmp_path):
    from src.scripts.backfill.processor import calculate_monthly_p95_threshold

    # 创建测试 CSV
    csv_path = tmp_path / "test.csv"
    # aggTrades CSV 格式: agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker
    csv_path.write_text(
        "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
        "1,50000.0,0.1,1,1,1704067200000,True\n"    # $5,000
        "2,50000.0,0.2,2,2,1704067260000,False\n"   # $10,000
        "3,50000.0,1.0,3,3,1704067320000,True\n"    # $50,000
        "4,50000.0,2.0,4,4,1704067380000,False\n"   # $100,000
        "5,50000.0,5.0,5,5,1704067440000,True\n"    # $250,000
    )

    threshold = calculate_monthly_p95_threshold(csv_path)

    # P95 应该接近最大值
    assert threshold > 50000
    assert threshold <= 250000


def test_process_agg_trades_to_flow(tmp_path):
    from src.scripts.backfill.processor import process_agg_trades_to_flow

    csv_path = tmp_path / "test.csv"
    csv_path.write_text(
        "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
        "1,50000.0,3.0,1,1,1704067200000,True\n"    # sell $150,000 @ hour 0
        "2,50000.0,2.0,2,2,1704067260000,False\n"   # buy $100,000 @ hour 0
        "3,50000.0,4.0,3,3,1704070800000,False\n"   # buy $200,000 @ hour 1
    )

    # 阈值 $50,000，所有交易都算大单
    flow = process_agg_trades_to_flow(csv_path, threshold=50000)

    # 返回 {timestamp_hour: net_flow}
    assert len(flow) == 2
    # Hour 0: buy $100,000 - sell $150,000 = -$50,000
    assert flow[1704067200000] == pytest.approx(-50000, rel=0.01)
    # Hour 1: buy $200,000 = +$200,000
    assert flow[1704070800000] == pytest.approx(200000, rel=0.01)
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/scripts/backfill/test_processor.py -v`
Expected: FAIL with "No module named 'src.scripts.backfill.processor'"

**Step 3: 实现处理器**

```python
# src/scripts/backfill/processor.py
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
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/scripts/backfill/test_processor.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/scripts/backfill/processor.py tests/scripts/backfill/test_processor.py
git commit -m "feat: 实现 aggTrades 处理器"
```

---

## Task 5: 实现极端事件检测器

**Files:**
- Create: `src/scripts/backfill/detector.py`
- Create: `tests/scripts/backfill/test_detector.py`

**Step 1: 写失败的测试**

```python
# tests/scripts/backfill/test_detector.py
import pytest


def test_calculate_rolling_percentile():
    from src.scripts.backfill.detector import calculate_rolling_percentile

    # 10 个数据点
    data = [(i * 3600000, float(i * 10)) for i in range(10)]  # 0, 10, 20, ..., 90

    # 在 idx=5 (value=50) 计算 3 天 (72h) 窗口
    # 窗口内有 idx 0-5 的数据: 0, 10, 20, 30, 40, 50
    # 50 比 5 个值大 (0,10,20,30,40)，百分位 = 5/6 * 100 = 83.3%
    pct = calculate_rolling_percentile(data, current_idx=5, window_hours=72)

    assert pct is not None
    assert pct == pytest.approx(83.3, abs=1)


def test_calculate_rolling_percentile_insufficient_data():
    from src.scripts.backfill.detector import calculate_rolling_percentile

    data = [(i * 3600000, float(i)) for i in range(5)]  # 只有 5 小时数据

    # 7 天窗口需要 168 小时，数据不足
    pct = calculate_rolling_percentile(data, current_idx=4, window_hours=168)

    assert pct is None


def test_detect_extreme_events():
    from src.scripts.backfill.detector import detect_extreme_events

    # 100 个数据点，最后 5 个是极端值
    data = [(i * 3600000, float(i)) for i in range(100)]
    # 修改最后几个为极端值
    data[95] = (95 * 3600000, 1000.0)
    data[97] = (97 * 3600000, 1000.0)
    data[99] = (99 * 3600000, 1000.0)

    events = detect_extreme_events(
        data,
        dimension="test_dim",
        symbol="BTC",
        window_hours=72,  # 3 天窗口
        threshold=90,
        cooldown_hours=1,
    )

    # 应该检测到极端事件（有冷却期，可能不是 3 个）
    assert len(events) >= 1
    assert all(e["percentile"] >= 90 for e in events)
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/scripts/backfill/test_detector.py -v`
Expected: FAIL with "No module named 'src.scripts.backfill.detector'"

**Step 3: 实现检测器**

```python
# src/scripts/backfill/detector.py
"""极端事件检测器"""

import logging
from typing import Any

from .config import COOLDOWN_HOURS, EXTREME_THRESHOLD, WINDOWS

logger = logging.getLogger(__name__)


def calculate_rolling_percentile(
    data: list[tuple[int, float]],  # [(timestamp_ms, value), ...]
    current_idx: int,
    window_hours: int,
) -> float | None:
    """
    计算滚动窗口百分位

    Args:
        data: 按时间排序的 (timestamp, value) 列表
        current_idx: 当前位置索引
        window_hours: 窗口大小（小时）

    Returns:
        百分位 (0-100)，数据不足返回 None
    """
    if current_idx < window_hours:
        return None

    # 获取窗口数据（不包含当前点，用于计算"历史"百分位）
    start_idx = max(0, current_idx - window_hours)
    window_data = [v for _, v in data[start_idx:current_idx]]

    if len(window_data) < window_hours:
        return None

    current_value = abs(data[current_idx][1])
    count_below = sum(1 for v in window_data if abs(v) < current_value)

    return count_below / len(window_data) * 100


def detect_extreme_events(
    data: list[tuple[int, float]],
    dimension: str,
    symbol: str,
    window_hours: int,
    threshold: float = EXTREME_THRESHOLD,
    cooldown_hours: int = COOLDOWN_HOURS,
) -> list[dict[str, Any]]:
    """
    检测极端事件

    Args:
        data: 按时间排序的 (timestamp, value) 列表
        dimension: 维度名称
        symbol: 交易对
        window_hours: 百分位窗口（小时）
        threshold: 极端阈值 (默认 90)
        cooldown_hours: 冷却期（小时）

    Returns:
        极端事件列表
    """
    events = []
    last_trigger_ts = 0
    cooldown_ms = cooldown_hours * 3600 * 1000

    for idx in range(window_hours, len(data)):
        ts, value = data[idx]

        # 检查冷却期
        if ts - last_trigger_ts < cooldown_ms:
            continue

        pct = calculate_rolling_percentile(data, idx, window_hours)
        if pct is None:
            continue

        if pct >= threshold:
            events.append({
                "symbol": symbol,
                "dimension": dimension,
                "window_days": window_hours // 24,
                "triggered_at": ts,
                "value": value,
                "percentile": pct,
            })
            last_trigger_ts = ts

    return events


def detect_all_windows(
    data: list[tuple[int, float]],
    dimension: str,
    symbol: str,
) -> list[dict[str, Any]]:
    """对所有窗口检测极端事件"""
    all_events = []

    for window_days, window_hours in WINDOWS.items():
        events = detect_extreme_events(
            data,
            dimension=dimension,
            symbol=symbol,
            window_hours=window_hours,
        )
        all_events.extend(events)
        logger.info(f"  {window_days}d window: {len(events)} events")

    return all_events
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/scripts/backfill/test_detector.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/scripts/backfill/detector.py tests/scripts/backfill/test_detector.py
git commit -m "feat: 实现极端事件检测器"
```

---

## Task 6: 实现价格回填器

**Files:**
- Create: `src/scripts/backfill/price_backfiller.py`
- Create: `tests/scripts/backfill/test_price_backfiller.py`

**Step 1: 写失败的测试**

```python
# tests/scripts/backfill/test_price_backfiller.py
import pytest
from pathlib import Path


def test_load_klines(tmp_path):
    from src.scripts.backfill.price_backfiller import load_klines

    # 创建测试 K 线 CSV
    csv_path = tmp_path / "klines.csv"
    # Binance klines CSV 格式: open_time,open,high,low,close,volume,close_time,...
    csv_path.write_text(
        "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
        "1704067200000,42000.0,42500.0,41800.0,42200.0,1000.0,1704070799999,42000000.0,5000,500.0,21000000.0,0\n"
        "1704070800000,42200.0,42800.0,42100.0,42600.0,1200.0,1704074399999,50400000.0,6000,600.0,25200000.0,0\n"
    )

    klines = load_klines([csv_path])

    assert len(klines) == 2
    assert klines[1704067200000] == 42200.0  # close price
    assert klines[1704070800000] == 42600.0


def test_backfill_prices():
    from src.scripts.backfill.price_backfiller import backfill_prices

    # K 线数据：每小时一个价格
    klines = {
        1704067200000: 42000.0,  # hour 0
        1704070800000: 42100.0,  # hour 1
        1704074400000: 42200.0,  # hour 2
        1704078000000: 42300.0,  # hour 3
        1704081600000: 42400.0,  # hour 4
        1704085200000: 42500.0,  # hour 5 (4h later)
        1704110400000: 42800.0,  # hour 12
        1704153600000: 43200.0,  # hour 24
        1704240000000: 43500.0,  # hour 48
    }

    event = {
        "triggered_at": 1704067200000,  # hour 0
        "value": 1000000.0,
    }

    backfilled = backfill_prices(event, klines)

    assert backfilled["price_at_trigger"] == 42000.0
    assert backfilled["price_4h"] == 42400.0
    assert backfilled["price_12h"] == 42800.0
    assert backfilled["price_24h"] == 43200.0
    assert backfilled["price_48h"] == 43500.0
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/scripts/backfill/test_price_backfiller.py -v`
Expected: FAIL with "No module named 'src.scripts.backfill.price_backfiller'"

**Step 3: 实现价格回填器**

```python
# src/scripts/backfill/price_backfiller.py
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
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/scripts/backfill/test_price_backfiller.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/scripts/backfill/price_backfiller.py tests/scripts/backfill/test_price_backfiller.py
git commit -m "feat: 实现价格回填器"
```

---

## Task 7: 重构主入口脚本

**Files:**
- Modify: `src/scripts/backfill_events.py`
- Modify: `tests/scripts/test_backfill_events.py`

**Step 1: 写失败的测试**

在 `tests/scripts/test_backfill_events.py` 添加：

```python
def test_parse_args_all_options():
    from src.scripts.backfill_events import parse_args

    args = parse_args(["--days", "180", "--symbol", "BTC", "--skip-download"])
    assert args.days == 180
    assert args.symbol == "BTC"
    assert args.skip_download is True


def test_parse_args_download_only():
    from src.scripts.backfill_events import parse_args

    args = parse_args(["--download-only"])
    assert args.download_only is True
```

**Step 2: 运行测试验证失败**

Run: `uv run pytest tests/scripts/test_backfill_events.py::test_parse_args_all_options -v`
Expected: FAIL with "Namespace has no attribute 'skip_download'"

**Step 3: 重构主脚本**

```python
# src/scripts/backfill_events.py
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
import sys
from collections.abc import Sequence
from pathlib import Path

from src.scripts.backfill.config import (
    CACHE_DIR,
    DIMENSIONS,
    PROCESSED_DIR,
    SYMBOLS,
    WINDOWS,
)
from src.scripts.backfill.detector import detect_all_windows
from src.scripts.backfill.downloader import Downloader
from src.scripts.backfill.price_backfiller import backfill_all_events, load_klines
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
    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append((int(row["timestamp"]), float(row["value"])))
    return data


async def run_download(downloader: Downloader, symbols: list[str], days: int) -> None:
    """执行下载步骤"""
    logger.info("[1/5] 下载数据...")

    for symbol in symbols:
        logger.info(f"  下载 {symbol}...")
        await downloader.download_all([symbol], days)

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


async def run_detect(symbols: list[str], dry_run: bool = False) -> list[dict]:
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
    all_klines = {}
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
            backfill_prices_single(event, all_klines[symbol])

    return events


def backfill_prices_single(event: dict, klines: dict[int, float]) -> None:
    """回填单个事件的价格"""
    from src.scripts.backfill.price_backfiller import backfill_prices
    backfill_prices(event, klines)


async def save_events(events: list[dict], db_path: str, dry_run: bool = False) -> None:
    """保存事件到数据库"""
    if dry_run:
        logger.info(f"[DRY RUN] 将插入 {len(events)} 个事件")
        for e in events[:5]:
            logger.info(f"  {e['symbol']} {e['dimension']} {e['window_days']}d: P{e['percentile']:.1f}")
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
    events = await run_detect(symbols, args.dry_run)

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
```

**Step 4: 运行测试验证通过**

Run: `uv run pytest tests/scripts/test_backfill_events.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/scripts/backfill_events.py tests/scripts/test_backfill_events.py
git commit -m "feat: 重构回测脚本主入口"
```

---

## Task 8: 集成测试和验证

**Step 1: 运行全部测试**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: 运行 lint 和类型检查**

Run: `uv run ruff check --fix . && uv run ruff format .`
Expected: No errors

Run: `uv run mypy src/scripts/backfill/`
Expected: No errors

**Step 3: 测试下载功能（小范围）**

Run: `uv run python -m src.scripts.backfill_events --days 30 --symbol BTC --download-only`
Expected: 成功下载 1-2 个月的数据

**Step 4: 测试完整流程（dry-run）**

Run: `uv run python -m src.scripts.backfill_events --days 30 --symbol BTC --dry-run`
Expected: 显示将要插入的事件数量

**Step 5: Commit**

```bash
git add .
git commit -m "chore: 代码格式化和类型检查通过"
```

---

## 后续任务（本计划不包含）

1. **添加更多维度处理** — OI 变化、资金费率、持仓比、Taker 比
2. **添加进度条显示** — 使用 rich 或 tqdm
3. **优化大文件处理** — 流式读取 aggTrades，减少内存占用
4. **添加断点续传状态** — 保存处理进度，支持中断后继续
