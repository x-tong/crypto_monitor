# 极端事件历史参考功能设计

## 背景

用户交易风格是摸顶抄底波段交易，当前系统能识别 P90+ 极端值，但缺少历史参照：
- 不知道「上次 P90+ 后市场怎么走的」
- 导致看到数据但不敢行动，错过时机

## 需求

| 项目 | 决定 |
|------|------|
| 触发条件 | P90+ 极端值（三窗口独立触发） |
| 百分位窗口 | 7天 / 30天 / 90天 |
| 显示内容 | 统计概率 + 最近案例 |
| 覆盖维度 | 全部（资金流向、OI、费率、爆仓、持仓比） |
| 历史回测 | 1 年，预填充极端事件 |
| 后续观察窗口 | 4h / 12h / 24h / 48h |
| 存储策略 | 只保留极端事件，原始数据仍 7 天 |

## 三窗口百分位设计

**为什么需要多窗口：**
- 7 天太短：容易被近期行情主导
- 90 天太长：信号不够敏感
- 三档组合可以判断「短期波动」vs「真正拐点」

**展示格式：**
```
主力净流向 (1h): +$47.7M
  P92(7d) / P85(30d) / P70(90d)
  🔴短期极端 🟡中期偏高 🟢长期正常
```

**触发逻辑：**
- 三个窗口独立判断，独立触发
- 任一窗口 P90+ 都会显示该窗口的历史参考
- 多个窗口同时 P90+ 时，分别显示各自的历史统计

## 数据模型

新增 `extreme_events` 表：

```sql
CREATE TABLE extreme_events (
    id INTEGER PRIMARY KEY,
    symbol TEXT,              -- BTC / ETH
    dimension TEXT,           -- flow_1h / oi_change / funding_rate / ...
    window_days INTEGER,      -- 百分位窗口：7 / 30 / 90
    triggered_at TIMESTAMP,   -- 触发时间
    value REAL,               -- 触发时的值（如 $47.7M）
    percentile REAL,          -- 百分位（如 90.5）
    price_at_trigger REAL,    -- 触发时价格
    price_4h REAL,            -- 4h 后价格（定时回填）
    price_12h REAL,           -- 12h 后价格
    price_24h REAL,           -- 24h 后价格
    price_48h REAL            -- 48h 后价格
);

CREATE INDEX idx_extreme_events_lookup
ON extreme_events(symbol, dimension, window_days, triggered_at);
```

**工作流程：**
1. 检测到任一窗口 P90+ → 插入记录（标记 window_days）
2. 同一时刻多个窗口 P90+ → 插入多条记录
3. 定时任务每小时检查，回填到期的后续价格
4. 查询时按 window_days 分组统计

## 历史回测

**数据来源（Binance API）：**
- `GET /fapi/v1/aggTrades` — 历史成交（可计算大单流向）
- `GET /fapi/v1/openInterestHist` — 历史 OI
- `GET /fapi/v1/fundingRate` — 历史资金费率
- `GET /futures/data/topLongShortPositionRatio` — 大户持仓比
- `GET /futures/data/globalLongShortAccountRatio` — 散户持仓比
- `GET /futures/data/takerlongshortRatio` — Taker 买卖比

**回测流程：**
1. 下载 1 年历史数据（按天/小时粒度）
2. 用当前系统的百分位算法，计算每个时间点的百分位
3. 识别 P90+ 时刻，生成极端事件记录
4. 从 K 线数据回填 4h/12h/24h/48h 后的价格

**限制：**
- 爆仓历史数据 Binance 不提供，只能从系统启动后积累
- 部分 API 有频率限制，回测需要分批执行

**回测脚本：**
```bash
uv run python -m src.scripts.backfill_events --days 365
```

## 展示格式

当报告/提醒中出现 P90+ 维度时，附加历史参考区块：

```
📊 BTC 市场洞察
━━━━━━━━━━━━━━━━━━━━
💰 资金动向 [实时]

  主力净流向 (1h): +$47.7M
    P92(7d) / P91(30d) / P70(90d)
    Binance: +$47.7M

  ┌─ 📜 历史参考 ────────────────
  │ 7d P90+ (近20次):
  │   24h: ↑45% / ↓55%  均值 -1.2%
  │
  │ 30d P90+ (近15次):
  │   24h: ↑35% / ↓65%  均值 -2.8%
  │
  │ 最近(30d): 1/28 $82,000 → 24h -4.8%
  └───────────────────────────────
```

**展示规则：**
- 每个维度显示三窗口百分位：P(7d) / P(30d) / P(90d)
- 任一窗口 P90+ 时，显示该窗口的历史参考
- 多个窗口同时 P90+ 时，分别显示各自统计
- 统计只用「已完成」的事件（有完整 48h 数据）
- 如果历史事件不足 5 次，显示「数据积累中」
- 「最近」案例优先显示较长窗口的（更有参考价值）

## 模块划分

**新增/修改的文件：**

```
src/
├── storage/
│   └── models.py          # 新增 ExtremeEvent 模型
│   └── database.py        # 新增事件表 CRUD
│
├── aggregator/
│   └── extreme_tracker.py # 新增：检测 P90+ 并记录事件
│   └── event_stats.py     # 新增：查询历史统计
│
├── collector/
│   └── event_backfiller.py # 新增：定时回填后续价格
│
├── notifier/
│   └── formatter.py       # 修改：P90+ 时附加历史参考
│
└── scripts/
    └── backfill_events.py # 新增：历史回测脚本
```

**运行时流程：**
1. `insight_trigger.py` 检测到 P90+ → 调用 `extreme_tracker.record()`
2. `event_backfiller` 每小时运行，回填到期的后续价格
3. `formatter.py` 渲染报告时，调用 `event_stats.get_summary()` 获取历史统计

**回测流程（一次性）：**
1. 运行 `backfill_events.py --days 365`
2. 脚本下载历史数据 → 计算百分位 → 生成事件 → 回填价格
3. 完成后系统立即可用

## 边界情况

| 情况 | 处理方式 |
|------|----------|
| 历史事件不足 5 次 | 显示「数据积累中，暂无统计」 |
| 回填任务失败（API 超时） | 重试 3 次，失败则标记该字段为 NULL，统计时跳过 |
| 同一维度+窗口短时间内多次触发 | 每个 (dimension, window_days) 组合独立冷却 1 小时 |
| 回测时百分位计算 | 回测时分别用 7/30/90 天滚动窗口计算，与实时逻辑一致 |
| 30/90 天窗口数据不足 | 回测初期跳过，等数据积累足够再计算 |

## 不做的事情

- 不预测未来价格走势（只展示历史统计）
- 不自动发出交易信号（纯数据工具定位不变）
- 不存储完整历史原始数据（只存极端事件）
