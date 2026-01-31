# Crypto Monitor

## WHAT

BTC/ETH 永续合约市场监控系统，通过 Telegram Bot 推送：
- 定时市场报告（价格、资金流向、OI、爆仓、情绪指标）
- 异常提醒（大单流向、OI 变化、爆仓异常）
- 价位提醒（用户自定义关键价位突破/跌破）

## WHY

- Binance Futures 数据源
- 大单过滤（P95 动态阈值）识别主力资金
- 百分位显示帮助判断当前数据在历史中的位置
- 纯数据工具，不做信号判断

## HOW

```
WebSocket 采集 → SQLite 存储 → 聚合计算 → Telegram 推送
```

**技术栈：**
- Python 3.14 (uv 虚拟环境)
- aiohttp + websockets（Binance API）
- python-telegram-bot
- aiosqlite
- pydantic + PyYAML（配置）

**项目结构：**
```
src/
├── collector/      # 数据采集（WebSocket + REST）
├── aggregator/     # 计算（flow, oi, liquidation, percentile）
├── alert/          # 告警（trigger, price_monitor）
├── notifier/       # Telegram Bot + 消息格式化
├── storage/        # SQLite 数据库
├── config.py       # 配置管理
└── main.py         # 入口
```

## 关键约束

### 数据
- 只监控 BTC/USDT:USDT 和 ETH/USDT:USDT 永续合约
- 大单阈值：动态 P95，默认 $100,000
- 数据保留 7 天，每日清理

### 告警
- 大单流向阈值：$10M/1h
- OI 变化阈值：3%/1h
- 爆仓阈值：$20M/1h
- 价位提醒冷却：1 小时

### 百分位级别
- 🟢 < P75（正常）
- 🟡 P75-P90（偏高）
- 🔴 > P90（极端）

### 开发
- TDD：先写测试再实现
- 类型注解：所有函数签名
- 异步：全程 async/await
- 测试命令：`uv run pytest tests/ -v`
- 格式化：`uv run ruff check --fix . && uv run ruff format .`
- 类型检查：`uv run mypy src/`

### git
- message：按照 docs\feature\chore\fix\test\ : 中文 message 的格式
- 及时更新 .gitignore

## 文档
- 外部文档优先使用 context7 mcp
- 设计文档：[docs/DESIGN.md](docs/DESIGN.md)
- 实现计划：[docs/plans/2026-01-30-crypto-monitor.md](./docs/plans/2026-01-30-crypto-monitor.md)
