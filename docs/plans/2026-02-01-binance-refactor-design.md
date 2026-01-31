# Binance 专注重构设计

## 背景

基于 [NEW_DESIGN.md](../NEW_DESIGN.md) 的讨论，对现有系统进行重构：
- 精简到只做 Binance
- 去掉 ccxt，自己封装 API
- 新增更细分的多空比数据
- 异常提醒改为分级推送

## 核心变化

| 维度 | 现有 → 重构后 |
|------|--------------|
| 交易所 | Binance + OKX → **只 Binance** |
| API 封装 | ccxt → **自己封装 Binance Futures API** |
| 多空比数据 | 1 个 → **4 个**（散户/大户账户/大户持仓/Taker） |
| 异常提醒 | 单维度触发 → **分级（观察/重要）** |

## 保留不变

- 大单过滤（P95 动态阈值）
- OI + 价格组合解读
- 百分位级别显示（🟢🟡🔴）
- 定时报告 + 按需查询 + 价位提醒
- SQLite 存储，7 天数据保留

## 删除

- 所有 OKX 相关代码
- ccxt 依赖
- 双交易所对比逻辑（"Binance vs OKX 一致/分歧"）

---

## Binance API 封装

### 新模块：`src/client/binance.py`

```python
class BinanceClient:
    """Binance Futures API 客户端"""

    BASE_URL = "https://fapi.binance.com"

    # REST API
    async def get_klines(symbol, interval) -> list[Kline]
    async def get_open_interest(symbol) -> OpenInterest
    async def get_open_interest_hist(symbol, period) -> list[OpenInterest]
    async def get_funding_rate(symbol) -> FundingRate
    async def get_premium_index(symbol) -> PremiumIndex

    # 多空比（4 个端点）
    async def get_global_long_short_ratio(symbol, period) -> LongShortRatio
    async def get_top_long_short_account_ratio(symbol, period) -> LongShortRatio
    async def get_top_long_short_position_ratio(symbol, period) -> LongShortRatio
    async def get_taker_long_short_ratio(symbol, period) -> TakerRatio

    # WebSocket
    async def subscribe_agg_trades(symbol, callback)  # 大单
    async def subscribe_force_order(callback)         # 爆仓
```

### 端点映射

| 方法 | Binance 端点 |
|------|-------------|
| `get_global_long_short_ratio` | `/futures/data/globalLongShortAccountRatio` |
| `get_top_long_short_account_ratio` | `/futures/data/topLongShortAccountRatio` |
| `get_top_long_short_position_ratio` | `/futures/data/topLongShortPositionRatio` |
| `get_taker_long_short_ratio` | `/futures/data/takerlongshortRatio` |
| `get_open_interest_hist` | `/futures/data/openInterestHist` |

---

## 数据库变化

### 新增表：多空比快照

```sql
CREATE TABLE long_short_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,              -- 'BTCUSDT'
    timestamp INTEGER NOT NULL,        -- 毫秒时间戳
    ratio_type TEXT NOT NULL,          -- 'global' | 'top_account' | 'top_position' | 'taker'
    long_ratio REAL NOT NULL,          -- 多头占比 (0-1)
    short_ratio REAL NOT NULL,         -- 空头占比 (0-1)
    long_short_ratio REAL NOT NULL,    -- 多空比
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_ls_symbol_type_time ON long_short_snapshots(symbol, ratio_type, timestamp);
```

### 修改

- `trades` 和 `liquidations` 表：`exchange` 字段保留，值固定为 `'binance'`
- `snapshots` 表：删除 `flow_1h_binance` / `flow_1h_okx` 字段

---

## 异常提醒分级

### 两级提醒

| 级别 | 触发条件 | 推送方式 |
|------|---------|---------|
| 📢 观察 | 单维度 > P90 | 普通消息 |
| 🚨 重要 | ≥3 个维度同时 > P90 | 普通消息 + 强调标记 |

### 监控维度（共 7 个）

1. 主力资金流向（大单净流入/流出）
2. OI 变化率
3. 爆仓量
4. 资金费率
5. 散户多空比 (`global`)
6. 大户多空比 (`top_position`)
7. Taker 买卖比

### 判断逻辑

```python
def check_alerts(symbol: str) -> list[Alert]:
    dimensions = [
        ("主力资金", get_flow_percentile(symbol)),
        ("OI变化", get_oi_change_percentile(symbol)),
        ("爆仓", get_liquidation_percentile(symbol)),
        ("资金费率", get_funding_percentile(symbol)),
        ("散户多空比", get_global_ls_percentile(symbol)),
        ("大户持仓比", get_top_position_percentile(symbol)),
        ("Taker买卖比", get_taker_percentile(symbol)),
    ]

    extreme = [(name, p) for name, p in dimensions if p > 90]

    if len(extreme) >= 3:
        return [Alert(level="important", dimensions=extreme)]
    elif extreme:
        return [Alert(level="observe", dimensions=extreme)]
    return []
```

### 消息格式

**观察提醒：**
```
📢 BTC 观察提醒

主力资金 1h 净流出 $8.2M 🔴 P92

💵 $103,850 (-0.5% 1h)
⏰ 2026-01-30 14:32 UTC
```

**重要提醒：**
```
🚨 BTC 重要提醒 - 3 维度共振

• 主力资金 1h: -$15.2M 🔴 P96
• OI 变化 1h: +4.2% 🔴 P94
• 爆仓 1h: $35M 🔴 P95

💵 $101,200 (-2.8% 1h)
⏰ 2026-01-30 14:32 UTC
```

---

## 代码结构变化

### 新增

```
src/
├── client/
│   ├── __init__.py
│   └── binance.py          # Binance API 封装
```

### 删除

```
src/collector/
├── okx_trades.py           # OKX 相关
├── binance_trades.py       # ccxt 实现
```

### 修改

| 文件 | 变化 |
|------|------|
| `collector/binance_liq.py` | 保留，已是原生 WebSocket |
| `collector/indicator_fetcher.py` | 重写，改用 `BinanceClient` |
| `aggregator/flow.py` | 去掉交易所区分逻辑 |
| `alert/trigger.py` | 新增分级判断 + 多维度共振检测 |
| `notifier/telegram.py` | 新增观察/重要两种消息格式 |
| `storage/database.py` | 新增 `long_short_snapshots` 表操作 |
| `config.py` | 去掉 OKX 配置，新增多空比采集配置 |

### 依赖变化

删除：
- `ccxt`

新增：
- `aiohttp`

---

## 配置变化

### 删除

```yaml
exchanges:
  okx:
    enabled: true
```

### 新增

```yaml
long_short_ratio:
  periods:
    - "15m"
    - "1h"
  fetch_interval_minutes: 5

alerts:
  observe:
    enabled: true
    percentile_threshold: 90
  important:
    enabled: true
    percentile_threshold: 90
    min_dimensions: 3
```

---

## 实施步骤

1. **新建 `src/client/binance.py`** — 封装 Binance Futures API
2. **删除 OKX 相关代码** — `okx_trades.py`、ccxt 依赖
3. **重写 `indicator_fetcher.py`** — 改用 BinanceClient，新增 4 种多空比采集
4. **数据库迁移** — 新增 `long_short_snapshots` 表
5. **修改 `trigger.py`** — 新增分级 + 共振逻辑
6. **修改 `telegram.py`** — 观察/重要消息格式
7. **更新配置和测试**

---

**设计版本**: v1.0
**创建时间**: 2026-02-01
