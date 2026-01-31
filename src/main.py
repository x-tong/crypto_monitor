# src/main.py
import asyncio
import logging
import signal
import time
from pathlib import Path
from typing import Any

from src.aggregator.flow import calculate_flow
from src.aggregator.liquidation import calculate_liquidations
from src.aggregator.oi import calculate_oi_change, interpret_oi_price
from src.alert.price_monitor import check_price_alerts
from src.collector.binance_liq import BinanceLiquidationCollector
from src.collector.binance_trades import BinanceTradesCollector
from src.collector.indicator_fetcher import IndicatorFetcher
from src.collector.okx_trades import OKXTradesCollector
from src.config import Config, load_config
from src.notifier.formatter import format_report
from src.notifier.telegram import TelegramNotifier
from src.storage.database import Database
from src.storage.models import Liquidation, PriceAlert, Trade

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CryptoMonitor:
    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.database.path)
        self.notifier = TelegramNotifier(config.telegram.bot_token, config.telegram.chat_id)
        self.indicator_fetcher = IndicatorFetcher(config.symbols)
        self.collectors: list[Any] = []
        self.running = False
        self.start_time = time.time()

    async def init(self) -> None:
        # Ensure data directory exists
        Path(self.config.database.path).parent.mkdir(parents=True, exist_ok=True)

        await self.db.init()
        await self.indicator_fetcher.init()

        # Setup collectors
        for symbol in self.config.symbols:
            if self.config.exchanges.binance.enabled:
                self.collectors.append(
                    BinanceTradesCollector(
                        symbol=symbol,
                        threshold_usd=self.config.thresholds.default_usd,
                        on_trade=self._on_trade,
                    )
                )
            if self.config.exchanges.okx.enabled:
                self.collectors.append(
                    OKXTradesCollector(
                        symbol=symbol,
                        threshold_usd=self.config.thresholds.default_usd,
                        on_trade=self._on_trade,
                    )
                )

        if self.config.exchanges.binance.enabled:
            self.collectors.append(
                BinanceLiquidationCollector(
                    symbols=self.config.symbols,
                    on_liquidation=self._on_liquidation,
                )
            )

        # Setup Telegram callbacks
        self.notifier.on_watch = self._on_watch
        self.notifier.on_unwatch = self._on_unwatch
        self.notifier.on_list = self._on_list
        self.notifier.on_report = self._on_report
        self.notifier.on_status = self._on_status

    async def _on_trade(self, trade: Trade) -> None:
        await self.db.insert_trade(trade)
        logger.debug(f"Trade: {trade.exchange} {trade.symbol} {trade.side} ${trade.value_usd:,.0f}")

    async def _on_liquidation(self, liq: Liquidation) -> None:
        await self.db.insert_liquidation(liq)
        logger.debug(f"Liquidation: {liq.exchange} {liq.symbol} {liq.side} ${liq.value_usd:,.0f}")

    async def _on_watch(self, symbol: str, price: float) -> None:
        # Get current price to determine position
        indicators = await self.indicator_fetcher.fetch_indicators(f"{symbol}/USDT:USDT")
        current_price = indicators.futures_price if indicators else 0
        position = "above" if current_price > price else "below"

        alert = PriceAlert(
            id=None,
            symbol=symbol,
            price=price,
            last_position=position,
            last_triggered_at=None,
        )
        await self.db.insert_price_alert(alert)

    async def _on_unwatch(self, symbol: str, price: float) -> None:
        await self.db.delete_price_alert(symbol, price)

    async def _on_list(self) -> str:
        lines = ["📋 当前监控价位\n"]
        for symbol in ["BTC", "ETH"]:
            alerts = await self.db.get_price_alerts(symbol)
            if alerts:
                lines.append(f"{symbol}:")
                for alert in alerts:
                    lines.append(f"  • {int(alert.price)}")
                lines.append("")
        return "\n".join(lines) if len(lines) > 1 else "暂无监控价位"

    async def _on_report(self, symbol: str) -> str:
        return await self._generate_report(f"{symbol}/USDT:USDT")

    async def _on_status(self) -> str:
        uptime = time.time() - self.start_time
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)

        return f"""🔧 系统状态

运行时间: {days}d {hours}h {minutes}m
数据连接: 🟢 正常

监控币种: {", ".join(self.config.symbols)}
"""

    async def _generate_report(self, symbol: str) -> str:
        # Fetch current data
        trades_1h = await self.db.get_trades(symbol, hours=1)
        trades_4h = await self.db.get_trades(symbol, hours=4)
        trades_24h = await self.db.get_trades(symbol, hours=24)

        flow_1h = calculate_flow(trades_1h)
        flow_4h = calculate_flow(trades_4h)
        flow_24h = calculate_flow(trades_24h)

        liqs_1h = await self.db.get_liquidations(symbol, hours=1)
        liqs_4h = await self.db.get_liquidations(symbol, hours=4)
        liq_stats_1h = calculate_liquidations(liqs_1h)
        liq_stats_4h = calculate_liquidations(liqs_4h)

        current_oi = await self.db.get_latest_oi(symbol)
        past_oi_1h = await self.db.get_oi_at(symbol, hours_ago=1)
        past_oi_4h = await self.db.get_oi_at(symbol, hours_ago=4)
        oi_change_1h = calculate_oi_change(current_oi, past_oi_1h)
        oi_change_4h = calculate_oi_change(current_oi, past_oi_4h)

        indicators = await self.indicator_fetcher.fetch_indicators(symbol)

        # Calculate percentiles (simplified - would use historical data in production)
        data = {
            "symbol": symbol.split("/")[0],
            "price": indicators.futures_price if indicators else 0,
            "price_change_1h": 0,  # Would calculate from historical prices
            "price_change_24h": 0,
            "flow_1h": flow_1h.net,
            "flow_1h_pct": 50,  # Would calculate from historical data
            "flow_4h": flow_4h.net,
            "flow_4h_pct": 50,
            "flow_24h": flow_24h.net,
            "flow_24h_pct": 50,
            "flow_binance": flow_1h.by_exchange.get("binance", 0),
            "flow_okx": flow_1h.by_exchange.get("okx", 0),
            "oi_value": current_oi.open_interest_usd if current_oi else 0,
            "oi_change_1h": oi_change_1h,
            "oi_change_1h_pct": 50,
            "oi_change_4h": oi_change_4h,
            "oi_change_4h_pct": 50,
            "oi_interpretation": interpret_oi_price(oi_change_1h, 0),
            "liq_1h_total": liq_stats_1h.total,
            "liq_1h_pct": 50,
            "liq_1h_long": liq_stats_1h.long,
            "liq_1h_short": liq_stats_1h.short,
            "liq_4h_total": liq_stats_4h.total,
            "liq_4h_pct": 50,
            "liq_4h_long": liq_stats_4h.long,
            "liq_4h_short": liq_stats_4h.short,
            "funding_rate": indicators.funding_rate if indicators else 0,
            "funding_rate_pct": 50,
            "long_short_ratio": indicators.long_short_ratio if indicators else 1,
            "long_short_ratio_pct": 50,
            "spot_perp_spread": indicators.spot_perp_spread if indicators else 0,
            "spot_perp_spread_pct": 50,
        }

        return format_report(data)

    async def _scheduled_report(self) -> None:
        interval = self.config.intervals.report_hours * 3600
        while self.running:
            await asyncio.sleep(interval)
            for symbol in self.config.symbols:
                try:
                    report = await self._generate_report(symbol)
                    await self.notifier.send_message(report)
                except Exception as e:
                    logger.error(f"Failed to send report for {symbol}: {e}")

    async def _fetch_indicators(self) -> None:
        interval = self.config.intervals.oi_fetch_minutes * 60
        while self.running:
            try:
                oi_snapshots = await self.indicator_fetcher.fetch_all_oi()
                for oi in oi_snapshots:
                    await self.db.insert_oi_snapshot(oi)
            except Exception as e:
                logger.error(f"Failed to fetch indicators: {e}")
            await asyncio.sleep(interval)

    async def _check_alerts(self) -> None:
        while self.running:
            await asyncio.sleep(60)  # Check every minute

            for symbol in self.config.symbols:
                try:
                    # Check price alerts
                    short_symbol = symbol.split("/")[0]
                    price_alerts = await self.db.get_price_alerts(short_symbol)
                    indicators = await self.indicator_fetcher.fetch_indicators(symbol)

                    if indicators and price_alerts:
                        triggered = check_price_alerts(
                            price_alerts,
                            indicators.futures_price,
                            self.config.price_alerts.cooldown_minutes * 60,
                        )
                        for result in triggered:
                            # Update alert state
                            new_position = (
                                "above" if indicators.futures_price > result.price else "below"
                            )
                            await self.db.update_price_alert(
                                result.alert_id,
                                position=new_position,
                                triggered_at=int(time.time()),
                            )
                            # Send notification
                            # ... (would gather data and format)
                except Exception as e:
                    logger.error(f"Failed to check alerts for {symbol}: {e}")

    async def run(self) -> None:
        await self.init()
        self.running = True

        # Start collectors
        for collector in self.collectors:
            await collector.start()

        # Start Telegram bot
        await self.notifier.start_polling()

        # Start background tasks
        tasks = [
            asyncio.create_task(self._scheduled_report()),
            asyncio.create_task(self._fetch_indicators()),
            asyncio.create_task(self._check_alerts()),
        ]

        logger.info("Crypto Monitor started")

        # Wait for shutdown signal
        stop_event = asyncio.Event()
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()

        # Cleanup
        self.running = False
        for task in tasks:
            task.cancel()
        for collector in self.collectors:
            await collector.stop()
        await self.notifier.stop_polling()
        await self.indicator_fetcher.close()
        await self.db.close()

        logger.info("Crypto Monitor stopped")


async def main() -> None:
    config = load_config(Path("config.yaml"))
    monitor = CryptoMonitor(config)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
