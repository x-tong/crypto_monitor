## 系统设计总结

### 定位
**关键位置验证器** —— 当你到达关键价格准备交易时，验证当前仓位结构是否支持你的判断。

### 技术选型
- 自己封装 Binance Futures API
- 不用 ccxt
- 只做 Binance 一个交易所

### 数据源

| 维度 | 端点 | 周期 |
|------|------|------|
| 散户多空比 | `globalLongShortAccountRatio` | 15m / 1h |
| 大户多空比（账户） | `topLongShortAccountRatio` | 15m / 1h |
| 大户多空比（持仓） | `topLongShortPositionRatio` | 15m / 1h |
| OI | `openInterest` + `openInterestHist` | 实时 + 历史 |
| 资金费率 | `fundingRate` + `premiumIndex` | 实时 + 历史 |
| Taker 买卖量 | `takerlongshortRatio` | 15m / 1h |
| 实时清算 | WebSocket `!forceOrder@arr` | 实时 |
| 价格 | `klines` | 15m / 1h |

### 输出
- **状态报告**，不是交易信号
- 决策权留给你

### 使用模式
| 模式 | 触发 | 输出 |
|------|------|------|
| 按需查询 | 你主动调用 | 完整状态报告 |
| 持续监控 | 后台运行 | 多维度共振时提醒 |

### 异常提醒逻辑
- 每个维度用**统计分位数**判断是否极端（相对过去 N 天）
- **≥3 个维度同时极端**才触发提醒

### 迭代路径
1. 先全部采集，全部呈现
2. 实战中记录 + 复盘
3. 砍掉没用的，强化有用的