# 回测脚本完善设计

## 概述

完善 `src/scripts/backfill_events.py`，实现历史极端事件回测，为系统预填充 1 年的极端事件数据。

## 设计决策

| 项目 | 决定 |
|------|------|
| 回测范围 | 全量（包括资金流向） |
| 资金流向阈值 | 按月计算 P95 |
| 时间粒度 | 1 小时 |
| 数据获取 | Binance 数据存档 + API |
| 缓存策略 | 本地文件缓存，支持断点续传 |

## 数据下载

**数据源：**

| 数据 | 来源 | 说明 |
|------|------|------|
| aggTrades | data.binance.vision | 月度 zip 下载 |
| klines 1h | data.binance.vision | 月度 zip 下载 |
| openInterestHist | Binance API | 5 分钟粒度 |
| fundingRate | Binance API | 8 小时粒度 |
| topLongShortPositionRatio | Binance API | 5 分钟粒度 |
| globalLongShortAccountRatio | Binance API | 5 分钟粒度 |
| takerlongshortRatio | Binance API | 5 分钟粒度 |

**缓存目录：**

```
data/backfill_cache/
├── aggTrades/
│   ├── BTCUSDT-aggTrades-2025-02.csv
│   └── ...
├── klines/
│   └── BTCUSDT-1h-2025-02.csv
├── indicators/
│   ├── openInterestHist_BTCUSDT.jsonl
│   ├── fundingRate_BTCUSDT.jsonl
│   └── ...
└── download_progress.json
```

**预计：**
- 磁盘空间：5-6 GB（压缩后）
- 下载时间：10-30 分钟

## 数据处理

**aggTrades → 资金流向：**

1. 按月加载 CSV
2. 计算该月所有成交的 USD 价值
3. 取 P95 作为该月大单阈值
4. 过滤大单（>= P95）
5. 按小时聚合：`sum(buy) - sum(sell) = net_flow_1h`

**其他指标：**

| 指标 | 处理方式 |
|------|---------|
| OI 变化 | 相邻小时 OI 差值百分比 |
| 资金费率 | 直接使用原始值 |
| 大户持仓比 | 直接使用 longShortRatio |
| 散户持仓比 | 直接使用 longShortRatio |
| Taker 比 | 直接使用 buySellRatio |

**中间文件：**

```
data/backfill_cache/processed/
├── flow_1h_BTCUSDT.csv
├── oi_change_1h_BTCUSDT.csv
├── funding_rate_BTCUSDT.csv
├── top_position_ratio_BTCUSDT.csv
├── global_account_ratio_BTCUSDT.csv
└── taker_ratio_BTCUSDT.csv
```

格式：`timestamp,value`，按时间排序，1 小时一条。

## 百分位计算与事件识别

**滚动窗口百分位：**

```
对于每个时间点 t：
  - 7d 窗口：取 t-168h 到 t-1h 的数据
  - 30d 窗口：取 t-720h 到 t-1h 的数据
  - 90d 窗口：取 t-2160h 到 t-1h 的数据

  窗口内数据不足则跳过
```

**极端事件识别：**

```
对于每个 (symbol, dimension, window) 组合：
  遍历每个小时：
    if percentile >= 90:
      if 距离上次触发 >= 1 小时:
        记录极端事件到 extreme_events 表
```

**预计事件数量：** 10,000-18,000 个

## 价格回填

从 klines 回填后续价格：

```
price_at_trigger = kline[triggered_at].close
price_4h  = kline[triggered_at + 4h].close
price_12h = kline[triggered_at + 12h].close
price_24h = kline[triggered_at + 24h].close
price_48h = kline[triggered_at + 48h].close
```

边界处理：
- 最近 48h 内的事件：后续价格留 NULL
- kline 缺失：该字段留 NULL

## 命令行接口

```bash
# 完整回测（默认 365 天）
uv run python -m src.scripts.backfill_events

# 指定天数
uv run python -m src.scripts.backfill_events --days 180

# 只处理特定 symbol
uv run python -m src.scripts.backfill_events --symbol BTC

# 跳过下载（使用已有缓存）
uv run python -m src.scripts.backfill_events --skip-download

# 只下载不处理
uv run python -m src.scripts.backfill_events --download-only

# 清理缓存
uv run python -m src.scripts.backfill_events --clean-cache
```

## 执行流程

```
[1/5] 下载数据...
  ├─ aggTrades: 12/12 months ✓
  ├─ klines: 12/12 months ✓
  └─ indicators: 6/6 types ✓

[2/5] 处理 aggTrades → 资金流向...
  ├─ BTCUSDT: 计算月度 P95 阈值...
  └─ ETHUSDT: 计算月度 P95 阈值...

[3/5] 计算百分位...
  └─ 36 组合 × 8760 小时...

[4/5] 识别极端事件...
  └─ 发现 12,345 个事件

[5/5] 回填后续价格...
  └─ 已更新 12,100 个事件

完成！耗时 ~25 分钟
```

## 模块结构

```
src/scripts/
├── backfill_events.py      # 主入口
├── backfill/
│   ├── __init__.py
│   ├── downloader.py       # 数据下载（存档 + API）
│   ├── processor.py        # 数据处理（aggTrades → flow）
│   ├── calculator.py       # 百分位计算
│   ├── detector.py         # 极端事件识别
│   └── backfiller.py       # 价格回填
```
