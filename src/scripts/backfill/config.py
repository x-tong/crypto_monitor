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
    7: 7 * 24,  # 168 小时
    30: 30 * 24,  # 720 小时
    90: 90 * 24,  # 2160 小时
}

# 极端事件阈值
EXTREME_THRESHOLD = 90

# 冷却期（小时）
COOLDOWN_HOURS = 1
