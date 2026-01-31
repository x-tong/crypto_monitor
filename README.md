# Crypto Monitor

BTC/ETH 永续合约市场监控系统，通过 Telegram Bot 推送市场数据。

## 功能

- **定时报告**: 价格、主力资金流向、OI、爆仓、情绪指标
- **异常提醒**: 大单流向/OI 变化/爆仓异常时自动触发
- **价位提醒**: 自定义关键价位，突破/跌破时推送

### 数据特点

| 特性 | 说明 |
|------|------|
| 数据源 | Binance Futures |
| 主力识别 | 大单过滤 (动态 P95 阈值) |
| 百分位显示 | 当前数据在 7 天历史中的位置 |

## 技术栈

- Python 3.14 + uv
- aiohttp + websockets (Binance API)
- python-telegram-bot
- aiosqlite
- pydantic + PyYAML

## 安装

```bash
# 克隆项目
git clone https://github.com/your-repo/crypto_monitor.git
cd crypto_monitor

# 安装依赖
uv sync

# 复制配置文件
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 Telegram Bot Token 和 Chat ID
```

## 运行

```bash
# 直接运行
uv run python -m src.main

# 或使用 Docker
docker-compose up -d
```

## 配置

编辑 `config.yaml`:

```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

# 监控币种
symbols:
  - BTC/USDT:USDT
  - ETH/USDT:USDT

# 告警阈值
alerts:
  whale_flow:
    threshold_usd: 10000000    # 1h 大单 > $10M
  oi_change:
    threshold_pct: 3           # 1h OI 变化 > 3%
  liquidation:
    threshold_usd: 20000000    # 1h 爆仓 > $20M

# 报告间隔
intervals:
  report_hours: 8
```

完整配置参考 [config.example.yaml](config.example.yaml)。

## Telegram 命令

| 命令 | 说明 |
|------|------|
| `/watch BTC 100000` | 添加价位监控 |
| `/unwatch BTC 100000` | 取消价位监控 |
| `/list` | 查看监控价位 |
| `/report BTC` | 手动拉取报告 |
| `/status` | 系统状态 |

## 输出示例

### 定时报告

```
📊 BTC 市场快照
⏰ 2026-01-30 08:00 UTC

💵 $104,230 (+1.2% 1h / +3.5% 24h)

💰 主力资金 (大单净流向):
  1h: +$5.2M 🟢 P62 | 4h: +$18.3M 🟡 P78
  Binance: +$28M

📈 持仓量 (OI): $18.2B
  1h: +1.2% 🟢 P58 | 4h: +2.3% 🟡 P76
  → 价格↑ OI↑ = 新多入场

💥 爆仓 1h: $7.4M 🟢 P52 (多$2.1M / 空$5.3M)

📊 资金费率: -0.01% 🟢 (空头付费)
```

### 百分位级别

| 级别 | 百分位 | 含义 |
|------|--------|------|
| 🟢 | < P75 | 正常 |
| 🟡 | P75-P90 | 偏高 |
| 🔴 | > P90 | 极端 |

## 项目结构

```
src/
├── collector/      # WebSocket + REST 数据采集
├── aggregator/     # 资金流向/OI/爆仓计算
├── alert/          # 异常检测、价位监控
├── notifier/       # Telegram Bot
├── storage/        # SQLite 数据库
├── config.py       # 配置管理
└── main.py         # 入口
```

## 开发

```bash
# 测试
uv run pytest tests/ -v

# 格式化
uv run ruff check --fix . && uv run ruff format .

# 类型检查
uv run mypy src/
```

## 文档

- [设计文档](docs/DESIGN.md)
- [实现计划](docs/plans/2026-01-30-crypto-monitor.md)

## License

MIT
