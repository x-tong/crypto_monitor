# 加密货币市场监控系统 - 设计文档

## 1. 概述

实时监控 BTC/ETH 的主力资金流向、持仓变化、爆仓数据和市场情绪指标，通过 Telegram Bot 推送定时报告和异常提醒。

**定位：数据聚合和推送工具，辅助用户自行判断。**

## 2. 需求摘要

| 项目 | 规格 |
|------|------|
| 数据源 | Binance + OKX 双交易所 |
| 币种 | BTC/USDT, ETH/USDT (永续合约) |
| 主力识别 | 大额 Taker 订单，动态阈值 P95 |
| 监控数据 | 主力资金流向、OI 变化、爆仓、资金费率、多空比、现货-合约价差 |
| 输出 | TG Bot (定时报告 + 异常提醒 + 价位提醒) |

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Crypto Monitor                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │  Binance   │  │  Binance   │  │    OKX     │  │  REST API  │    │
│  │ WebSocket  │  │ WebSocket  │  │ WebSocket  │  │ (定时获取)  │    │
│  │ (trades)   │  │(forceOrder)│  │ (trades)   │  │            │    │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘    │
│        │               │               │               │            │
│        └───────┬───────┴───────┬───────┴───────┬───────┘            │
│                ▼               ▼               ▼                    │
│      ┌──────────────────────────────────────────────────┐           │
│      │                Data Collector                    │           │
│      │  - trades: 大单过滤 (P95)                        │           │
│      │  - liquidations: 实时爆仓                        │           │
│      │  - OI/指标: 定时拉取 (5min)                      │           │
│      └────────────────────────┬─────────────────────────┘           │
│                               ▼                                     │
│      ┌──────────────────────────────────────────────────┐           │
│      │               Data Aggregator                    │           │
│      │  - 计算主力资金流向 (1h/4h/24h)                   │           │
│      │  - 计算 OI 变化率                                │           │
│      │  - 统计爆仓数据                                  │           │
│      │  - 整合情绪指标                                  │           │
│      └────────────────────────┬─────────────────────────┘           │
│                               ▼                                     │
│      ┌──────────────────────────────────────────────────┐           │
│      │              Telegram Notifier                   │           │
│      │  - 定时报告 (每 8h)                               │           │
│      │  - 异常提醒 (阈值触发)                            │           │
│      └──────────────────────────────────────────────────┘           │
│                               │                                     │
│      ┌────────────────────────▼─────────────────────────┐           │
│      │                  SQLite DB                       │           │
│      │  - trades (大单, 滚动 7d)                         │           │
│      │  - liquidations (爆仓, 滚动 7d)                   │           │
│      │  - oi_snapshots (OI 快照)                        │           │
│      │  - snapshots (定时快照, 用于历史查询)             │           │
│      └──────────────────────────────────────────────────┘           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 4. 模块设计

### 4.1 项目结构

```
crypto_monitor/
├── src/
│   ├── __init__.py
│   ├── main.py                 # 入口
│   ├── config.py               # 配置管理
│   ├── collector/
│   │   ├── __init__.py
│   │   ├── base.py             # 基类
│   │   ├── binance_trades.py   # Binance trades WebSocket (ccxt)
│   │   ├── binance_liq.py      # Binance 爆仓 WebSocket (原生)
│   │   ├── okx_trades.py       # OKX trades WebSocket (ccxt)
│   │   └── indicator_fetcher.py# OI/指标 定时获取 (ccxt REST)
│   ├── aggregator/
│   │   ├── __init__.py
│   │   ├── flow.py             # 资金流向计算
│   │   ├── oi.py               # OI 变化计算
│   │   ├── liquidation.py      # 爆仓统计
│   │   ├── snapshot.py         # 快照生成
│   │   └── percentile.py       # 百分位计算
│   ├── alert/
│   │   ├── __init__.py
│   │   ├── trigger.py          # 异常触发检测
│   │   └── price_monitor.py    # 价位监控
│   ├── notifier/
│   │   ├── __init__.py
│   │   └── telegram.py         # TG Bot
│   ├── storage/
│   │   ├── __init__.py
│   │   └── database.py         # SQLite 操作
│   └── utils/
│       ├── __init__.py
│       └── helpers.py          # 工具函数
├── tests/
│   └── ...
├── config.example.yaml
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

### 4.2 数据库设计

```sql
-- 大单记录 (滚动保留 7 天)
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,           -- 'binance' | 'okx'
    symbol TEXT NOT NULL,             -- 'BTC/USDT:USDT'
    timestamp INTEGER NOT NULL,       -- 毫秒时间戳
    price REAL NOT NULL,
    amount REAL NOT NULL,
    side TEXT NOT NULL,               -- 'buy' | 'sell'
    value_usd REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_trades_symbol_time ON trades(symbol, timestamp);

-- 爆仓记录 (滚动保留 7 天)
CREATE TABLE liquidations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    side TEXT NOT NULL,               -- 'buy'=空头爆仓, 'sell'=多头爆仓
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    value_usd REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_liq_symbol_time ON liquidations(symbol, timestamp);

-- OI 快照 (每 5 分钟)
CREATE TABLE oi_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open_interest REAL NOT NULL,      -- 币本位
    open_interest_usd REAL NOT NULL,  -- USD
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_oi_symbol_time ON oi_snapshots(symbol, timestamp);

-- 市场快照 (每次报告时保存，便于历史查询)
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    price REAL NOT NULL,

    -- 主力资金
    flow_1h REAL,
    flow_4h REAL,
    flow_24h REAL,
    flow_1h_binance REAL,
    flow_1h_okx REAL,

    -- OI
    oi_value REAL,
    oi_change_1h REAL,
    oi_change_4h REAL,

    -- 爆仓
    liq_long_1h REAL,
    liq_short_1h REAL,
    liq_long_4h REAL,
    liq_short_4h REAL,

    -- 情绪指标
    funding_rate REAL,
    long_short_ratio REAL,
    spot_perp_spread REAL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_snapshot_symbol_time ON snapshots(symbol, timestamp);

-- 动态阈值
CREATE TABLE thresholds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    p95_value REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 价位监控
CREATE TABLE price_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,             -- 'BTC' | 'ETH'
    price REAL NOT NULL,              -- 目标价位
    last_position TEXT,               -- 'above' | 'below' (上次价格位置)
    last_triggered_at INTEGER,        -- 上次触发时间戳 (冷却用)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_price_alerts_symbol ON price_alerts(symbol);
```

### 4.3 核心计算

#### 4.3.1 主力资金流向

```python
def calculate_flow(symbol: str, hours: int) -> FlowResult:
    """计算指定窗口的大单净流向"""
    trades = db.get_trades(symbol, hours=hours)

    buy = sum(t.value_usd for t in trades if t.side == 'buy')
    sell = sum(t.value_usd for t in trades if t.side == 'sell')
    net = buy - sell

    return FlowResult(net=net, buy=buy, sell=sell)
```

#### 4.3.2 OI 变化

```python
def calculate_oi_change(symbol: str, hours: int) -> float:
    """计算 OI 变化率 (%)"""
    current = db.get_latest_oi(symbol)
    past = db.get_oi_at(symbol, hours_ago=hours)

    if not current or not past or past.value == 0:
        return 0.0

    return (current.value - past.value) / past.value * 100
```

#### 4.3.3 爆仓统计

```python
def get_liquidations(symbol: str, hours: int) -> LiqStats:
    """统计爆仓数据"""
    liqs = db.get_liquidations(symbol, hours=hours)

    long_liq = sum(l.value_usd for l in liqs if l.side == 'sell')
    short_liq = sum(l.value_usd for l in liqs if l.side == 'buy')

    return LiqStats(long=long_liq, short=short_liq)
```

#### 4.3.4 OI + 价格解读

```python
def interpret_oi_price(oi_change: float, price_change: float) -> str:
    """OI 与价格变化组合解读"""
    if oi_change > 1 and price_change > 0:
        return "新多入场"
    elif oi_change > 1 and price_change < 0:
        return "新空入场"
    elif oi_change < -1 and price_change > 0:
        return "空头平仓"
    elif oi_change < -1 and price_change < 0:
        return "多头平仓"
    else:
        return "持仓稳定"
```

### 4.4 异常提醒 (可配置)

```yaml
alerts:
  whale_flow:
    enabled: true
    threshold_usd: 10000000    # 1h 大单净流入/流出 > $10M
  oi_change:
    enabled: true
    threshold_pct: 3           # 1h OI 变化 > 3%
  liquidation:
    enabled: true
    threshold_usd: 20000000    # 1h 爆仓 > $20M
```

触发时推送：

```
⚠️ BTC 异常提醒

主力大单 1h 净流出 $15.2M 🔴 P96
Binance: -$10.1M | OKX: -$5.1M

当前价格: $103,850 (-0.8% 1h)

⏰ 2026-01-30 14:32 UTC
```

### 4.5 价位监控

用户通过 Telegram 命令设置关键价位，价格突破/跌破时推送市场数据快照。

**触发逻辑：**
- 双向监控：记录设置时的价格位置（高于/低于目标价）
- 从上方跌破 → 提醒"跌破 xxx"
- 从下方突破 → 提醒"突破 xxx"
- 触发后保留监控，设置冷却时间（默认 1 小时）避免震荡时刷屏

```python
def check_price_alerts(symbol: str, current_price: float) -> list[Alert]:
    """检查价位是否触发"""
    alerts = db.get_price_alerts(symbol)
    triggered = []

    for alert in alerts:
        # 检查冷却
        if alert.last_triggered_at:
            cooldown = config.price_alerts.cooldown_minutes * 60
            if time.time() - alert.last_triggered_at < cooldown:
                continue

        # 检查突破/跌破
        if alert.last_position == 'below' and current_price >= alert.price:
            triggered.append(Alert(type='breakout', price=alert.price))
            db.update_alert(alert.id, position='above', triggered_at=now)
        elif alert.last_position == 'above' and current_price <= alert.price:
            triggered.append(Alert(type='breakdown', price=alert.price))
            db.update_alert(alert.id, position='below', triggered_at=now)

    return triggered
```

### 4.6 数据级别 (百分位)

所有指标显示 Emoji + 百分位，帮助快速判断当前数据处于历史什么水平。

**级别划分：**

| 百分位 | Emoji | 含义 |
|--------|-------|------|
| < P75 | 🟢 | 正常范围 |
| P75 - P90 | 🟡 | 偏高，值得关注 |
| > P90 | 🔴 | 极端，需要注意 |

```python
def get_level_emoji(percentile: float) -> str:
    """根据百分位返回级别 emoji"""
    if percentile < 75:
        return "🟢"
    elif percentile < 90:
        return "🟡"
    else:
        return "🔴"

def calculate_percentile(value: float, history: list[float]) -> float:
    """计算当前值在历史数据中的百分位"""
    if not history:
        return 50.0
    count_below = sum(1 for h in history if h < abs(value))
    return count_below / len(history) * 100
```

百分位基于最近 7 天数据，每小时更新一次。

### 4.7 Telegram Bot 命令

| 命令 | 说明 |
|------|------|
| `/watch BTC 100000` | 添加 BTC 100000 价位监控 |
| `/unwatch BTC 100000` | 取消 BTC 100000 价位监控 |
| `/list` | 查看所有监控价位 |
| `/report BTC` | 手动拉取 BTC 报告 |
| `/status` | 查看系统运行状态 |

**/list 响应示例：**
```
📋 当前监控价位

BTC:
  • 100000
  • 95000
  • 108000

ETH:
  • 3200
  • 3500
```

**/status 响应示例：**
```
🔧 系统状态

运行时间: 3d 12h 25m
数据连接:
  Binance WS: 🟢 正常
  OKX WS: 🟢 正常

最后更新:
  Trades: 2s 前
  OI: 3m 前
  指标: 4m 前

数据库: 1.2GB (7d 数据)
```

### 4.8 配置文件

```yaml
# config.yaml
exchanges:
  binance:
    enabled: true
  okx:
    enabled: true

symbols:
  - BTC/USDT:USDT
  - ETH/USDT:USDT

thresholds:
  default_usd: 100000
  percentile: 95
  update_interval_hours: 1

intervals:
  oi_fetch_minutes: 5
  indicator_fetch_minutes: 5
  report_hours: 8
  cleanup_hours: 24

alerts:
  whale_flow:
    enabled: true
    threshold_usd: 10000000
  oi_change:
    enabled: true
    threshold_pct: 3
  liquidation:
    enabled: true
    threshold_usd: 20000000

telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

database:
  path: "data/monitor.db"
  retention_days: 7

# 价位监控
price_alerts:
  cooldown_minutes: 60            # 同一价位触发冷却时间

# 百分位计算
percentile:
  window_days: 7                  # 基于最近 7 天数据
  update_interval_minutes: 60     # 每小时更新一次

# 百分位级别划分
percentile_levels:
  normal_below: 75                # < P75 显示 🟢
  warning_below: 90               # P75-P90 显示 🟡, > P90 显示 🔴
```

## 5. 输出格式

### 5.1 定时报告 (可配置间隔)

```
📊 BTC 市场快照
⏰ 2026-01-30 08:00 UTC

💵 $104,230 (+1.2% 1h / +3.5% 24h)

━━━━━━━━━━━━━━━━━━━━
💰 主力资金 (大单净流向):
  1h: +$5.2M 🟢 P62 | 4h: +$18.3M 🟡 P78
  24h: +$42.1M 🟢 P55
  Binance: +$28M | OKX: +$14M ✓一致

━━━━━━━━━━━━━━━━━━━━
📈 持仓量 (OI): $18.2B
  1h: +1.2% 🟢 P58 | 4h: +2.3% 🟡 P76
  → 价格↑ OI↑ = 新多入场

━━━━━━━━━━━━━━━━━━━━
💥 爆仓:
  1h: $7.4M 🟢 P52 (多$2.1M / 空$5.3M)
  4h: $20.3M 🟡 P82 (多$8.2M / 空$12.1M)

━━━━━━━━━━━━━━━━━━━━
📊 情绪指标:
  资金费率: -0.01% 🟢 P48 (空头付费)
  多空比: 1.35 🟢 P62 (散户偏多)
  合约溢价: +0.05% 🟢 P44
```

### 5.2 异常提醒

```
⚠️ BTC 大单异常

1h 净流出 $15.2M 🔴 P96
  Binance: -$10.1M
  OKX: -$5.1M

💵 $103,850 (-0.8% 1h)
⏰ 2026-01-30 14:32 UTC
```

```
⚠️ ETH OI 异常

1h OI 变化: +4.2% 🔴 P94
当前 OI: $8.5B

💵 $3,420 (+0.5% 1h)
→ 价格↑ OI↑ = 新多入场

⏰ 2026-01-30 14:32 UTC
```

```
⚠️ BTC 爆仓异常

1h 总爆仓: $35.2M 🔴 P95
  多头爆仓: $28.1M (80%)
  空头爆仓: $7.1M

💵 $101,200 (-2.8% 1h)
⏰ 2026-01-30 14:32 UTC
```

### 5.3 价位提醒

```
📍 BTC 突破 100000

💵 当前: $100,150 (+0.3% 1h)

💰 主力资金 1h: +$3.2M 🟢 P62
📈 OI 变化 1h: +2.8% 🟡 P85
💥 爆仓 1h: $8.5M 🟢 P58 (多$3.2M / 空$5.3M)
📊 资金费率: +0.01% 🟢 P45

⏰ 2026-01-30 14:32 UTC
```

```
📍 ETH 跌破 3200

💵 当前: $3,185 (-0.5% 1h)

💰 主力资金 1h: -$2.1M 🟡 P78
📈 OI 变化 1h: -1.2% 🟢 P65
💥 爆仓 1h: $12.3M 🟡 P82 (多$9.1M / 空$3.2M)
📊 资金费率: -0.02% 🟢 P52

⏰ 2026-01-30 14:32 UTC
```

## 6. 部署

### 6.1 Docker Compose

```yaml
version: '3.8'

services:
  crypto-monitor:
    build: .
    container_name: crypto-monitor
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
    environment:
      - TZ=UTC
```

### 6.2 环境要求

- Python 3.11+
- 稳定网络连接

## 7. 后续扩展

- [ ] 信号逻辑 (基于数据积累后验证)
- [ ] Web 界面
- [ ] 更多币种
- [ ] 自定义提醒条件

---

**文档版本**: v2.1
**更新时间**: 2026-01-30
