# src/main.py
import asyncio
import logging
import signal
import time
from pathlib import Path
from typing import Any

from src.aggregator.event_stats import EventStats
from src.aggregator.extreme_tracker import ExtremeTracker
from src.aggregator.flow import calculate_flow
from src.aggregator.insight import calculate_change, calculate_divergence, generate_summary
from src.aggregator.liquidation import calculate_liquidations
from src.aggregator.oi import calculate_oi_change, interpret_oi_price
from src.alert.insight_trigger import check_insight_alerts
from src.alert.price_monitor import check_price_alerts
from src.alert.trigger import AlertLevel, check_tiered_alerts
from src.client.binance import BinanceClient
from src.collector.binance_liq import BinanceLiquidationCollector
from src.collector.binance_trades import BinanceTradesCollector
from src.collector.event_backfiller import EventBackfiller
from src.collector.indicator_fetcher import IndicatorFetcher
from src.config import Config, load_config
from src.notifier.formatter import (
    format_important_alert,
    format_insight_report_with_history,
    format_liquidation_alert,
    format_observe_alert,
    format_oi_alert,
    format_report,
    format_whale_alert,
)
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
        self.binance_client = BinanceClient()
        self.extreme_tracker = ExtremeTracker(self.db, cooldown_hours=1)
        self.event_stats = EventStats(self.db)
        self.event_backfiller = EventBackfiller(self.db, self.binance_client)
        self.collectors: list[Any] = []
        self.running = False
        self.start_time = time.time()

    async def init(self) -> None:
        # Ensure data directory exists
        Path(self.config.database.path).parent.mkdir(parents=True, exist_ok=True)

        await self.db.init()
        await self.indicator_fetcher.init()
        await self.binance_client.init()

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
        full_symbol = f"{symbol}/USDT:USDT"
        if self.config.insight.enabled:
            return await self._generate_insight_report(full_symbol)
        return await self._generate_report(full_symbol)

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
        from src.aggregator.percentile import calculate_percentile

        window_hours = self.config.percentile.window_days * 24

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

        # 获取历史数据用于百分位计算
        trades_history = await self.db.get_trades(symbol, hours=window_hours)
        liqs_history = await self.db.get_liquidations(symbol, hours=window_hours)

        # 按小时聚合历史 flow
        flow_history: list[float] = []
        hour_buckets: dict[int, list[float]] = {}
        for t in trades_history:
            hour = t.timestamp // 3600000
            if hour not in hour_buckets:
                hour_buckets[hour] = []
            net = t.value_usd if t.side == "buy" else -t.value_usd
            hour_buckets[hour].append(net)
        for nets in hour_buckets.values():
            flow_history.append(sum(nets))

        # 按小时聚合历史爆仓
        liq_history: list[float] = []
        liq_buckets: dict[int, float] = {}
        for liq in liqs_history:
            hour = liq.timestamp // 3600000
            liq_buckets[hour] = liq_buckets.get(hour, 0) + liq.value_usd
        liq_history = list(liq_buckets.values())

        # 计算 OI 变化历史
        oi_change_history: list[float] = []
        for h in range(1, min(window_hours, 48)):
            oi_h = await self.db.get_oi_at(symbol, hours_ago=h)
            oi_h_prev = await self.db.get_oi_at(symbol, hours_ago=h + 1)
            if oi_h and oi_h_prev and oi_h_prev.open_interest_usd > 0:
                change = (
                    (oi_h.open_interest_usd - oi_h_prev.open_interest_usd)
                    / oi_h_prev.open_interest_usd
                    * 100
                )
                oi_change_history.append(change)

        # 获取多空比历史
        ls_history = await self.db.get_long_short_snapshots(symbol, "global", hours=window_hours)
        ls_ratio_history = [s["long_short_ratio"] for s in ls_history]

        # 计算百分位
        flow_1h_pct = calculate_percentile(flow_1h.net, flow_history)
        flow_4h_pct = calculate_percentile(flow_4h.net, flow_history)
        flow_24h_pct = calculate_percentile(flow_24h.net, flow_history)
        oi_1h_pct = calculate_percentile(oi_change_1h, oi_change_history)
        oi_4h_pct = calculate_percentile(oi_change_4h, oi_change_history)
        liq_1h_pct = calculate_percentile(liq_stats_1h.total, liq_history)
        liq_4h_pct = calculate_percentile(liq_stats_4h.total, liq_history)
        funding_pct = calculate_percentile(
            indicators.funding_rate if indicators else 0,
            [-0.01, 0, 0.01, 0.02, 0.03, 0.05],
        )
        ls_pct = calculate_percentile(
            indicators.long_short_ratio if indicators else 1, ls_ratio_history
        )

        data = {
            "symbol": symbol.split("/")[0],
            "price": indicators.futures_price if indicators else 0,
            "price_change_1h": 0,
            "price_change_24h": 0,
            "flow_1h": flow_1h.net,
            "flow_1h_pct": flow_1h_pct,
            "flow_4h": flow_4h.net,
            "flow_4h_pct": flow_4h_pct,
            "flow_24h": flow_24h.net,
            "flow_24h_pct": flow_24h_pct,
            "flow_binance": flow_1h.by_exchange.get("binance", 0),
            "oi_value": current_oi.open_interest_usd if current_oi else 0,
            "oi_change_1h": oi_change_1h,
            "oi_change_1h_pct": oi_1h_pct,
            "oi_change_4h": oi_change_4h,
            "oi_change_4h_pct": oi_4h_pct,
            "oi_interpretation": interpret_oi_price(oi_change_1h, 0),
            "liq_1h_total": liq_stats_1h.total,
            "liq_1h_pct": liq_1h_pct,
            "liq_1h_long": liq_stats_1h.long,
            "liq_1h_short": liq_stats_1h.short,
            "liq_4h_total": liq_stats_4h.total,
            "liq_4h_pct": liq_4h_pct,
            "liq_4h_long": liq_stats_4h.long,
            "liq_4h_short": liq_stats_4h.short,
            "funding_rate": indicators.funding_rate if indicators else 0,
            "funding_rate_pct": funding_pct,
            "long_short_ratio": indicators.long_short_ratio if indicators else 1,
            "long_short_ratio_pct": ls_pct,
            "spot_perp_spread": indicators.spot_perp_spread if indicators else 0,
            "spot_perp_spread_pct": 50,  # 合约溢价暂无历史数据
        }

        return format_report(data)

    async def _generate_insight_report(self, symbol: str) -> str:
        """生成市场洞察报告"""
        from src.aggregator.percentile import calculate_percentile

        # 获取当前和历史市场指标
        current_mi = await self.db.get_latest_market_indicator(symbol)
        history_mi = await self.db.get_market_indicator_history(symbol, hours=24)

        if not current_mi:
            return await self._generate_report(symbol)  # 回退到旧报告

        # 获取 1h 前的指标用于计算变化
        mi_1h_ago = None
        one_hour_ago = int(time.time() * 1000) - 3600 * 1000
        for mi in history_mi:
            if mi.timestamp <= one_hour_ago:
                mi_1h_ago = mi
                break

        if not mi_1h_ago:
            mi_1h_ago = current_mi  # 数据不足时用当前值

        # 计算分歧历史
        divergence_history = [
            abs(mi.top_position_ratio - mi.global_account_ratio) for mi in history_mi
        ]

        divergence_result = calculate_divergence(
            current_mi.top_position_ratio,
            current_mi.global_account_ratio,
            divergence_history,
            self.config.insight.divergence.mild_percentile,
            self.config.insight.divergence.strong_percentile,
        )

        # 获取其他数据
        trades_1h = await self.db.get_trades(symbol, hours=1)
        flow_1h = calculate_flow(trades_1h)

        liqs_1h = await self.db.get_liquidations(symbol, hours=1)
        liq_stats = calculate_liquidations(liqs_1h)
        liq_long_ratio = liq_stats.long / liq_stats.total if liq_stats.total > 0 else 0.5

        current_oi = await self.db.get_latest_oi(symbol)
        past_oi_1h = await self.db.get_oi_at(symbol, hours_ago=1)
        # OI 变化：如果历史数据不足，返回 0 而非极端值
        if past_oi_1h and past_oi_1h.open_interest_usd > 0:
            oi_change_1h = calculate_oi_change(current_oi, past_oi_1h)
        else:
            oi_change_1h = 0.0

        indicators = await self.indicator_fetcher.fetch_indicators(symbol)

        # 计算变化
        top_change = calculate_change(current_mi.top_position_ratio, mi_1h_ago.top_position_ratio)
        global_change = calculate_change(
            current_mi.global_account_ratio, mi_1h_ago.global_account_ratio
        )
        taker_change = calculate_change(
            current_mi.taker_buy_sell_ratio, mi_1h_ago.taker_buy_sell_ratio
        )

        # 生成总结
        summary_data = {
            "top_ratio_change": top_change["diff"],
            "divergence": divergence_result["divergence"],
            "divergence_level": divergence_result["level"],
            "flow_1h": flow_1h.net,
            "liq_long_ratio": liq_long_ratio,
        }
        summary = generate_summary(summary_data)

        # 计算百分位所需的历史数据
        window_hours = self.config.percentile.window_days * 24

        # 从历史市场指标提取各维度历史
        top_pos_history = [mi.top_position_ratio for mi in history_mi]
        global_acc_history = [mi.global_account_ratio for mi in history_mi]
        taker_history = [mi.taker_buy_sell_ratio for mi in history_mi]

        # 获取 flow 历史
        trades_history = await self.db.get_trades(symbol, hours=window_hours)
        flow_history: list[float] = []
        hour_buckets: dict[int, list[float]] = {}
        for t in trades_history:
            hour = t.timestamp // 3600000
            if hour not in hour_buckets:
                hour_buckets[hour] = []
            net = t.value_usd if t.side == "buy" else -t.value_usd
            hour_buckets[hour].append(net)
        for nets in hour_buckets.values():
            flow_history.append(sum(nets))

        # 计算 OI 变化历史
        oi_change_history: list[float] = []
        for h in range(1, min(window_hours, 48)):
            oi_h = await self.db.get_oi_at(symbol, hours_ago=h)
            oi_h_prev = await self.db.get_oi_at(symbol, hours_ago=h + 1)
            if oi_h and oi_h_prev and oi_h_prev.open_interest_usd > 0:
                change = (
                    (oi_h.open_interest_usd - oi_h_prev.open_interest_usd)
                    / oi_h_prev.open_interest_usd
                    * 100
                )
                oi_change_history.append(change)

        # 计算百分位
        top_pos_pct = calculate_percentile(current_mi.top_position_ratio, top_pos_history)
        global_acc_pct = calculate_percentile(current_mi.global_account_ratio, global_acc_history)
        taker_pct = calculate_percentile(current_mi.taker_buy_sell_ratio, taker_history)
        flow_pct = calculate_percentile(flow_1h.net, flow_history)
        oi_pct = calculate_percentile(oi_change_1h, oi_change_history)
        # 资金费率使用业界标准范围
        funding_pct = calculate_percentile(
            indicators.funding_rate if indicators else 0,
            [-0.01, 0, 0.01, 0.02, 0.03, 0.05],
        )

        # 组装报告数据（使用三窗口百分位格式）
        short_symbol = symbol.split("/")[0]
        data = {
            "symbol": short_symbol,
            "price": indicators.futures_price if indicators else 0,
            "price_change_1h": 0,
            "summary": summary,
            # 大户 vs 散户
            "top_position_ratio": current_mi.top_position_ratio,
            "top_position_change": top_change["diff"],
            "top_position_pct": top_pos_pct,
            "global_account_ratio": current_mi.global_account_ratio,
            "global_account_change": global_change["diff"],
            "global_account_pct": global_acc_pct,
            "divergence": divergence_result["divergence"],
            "divergence_pct": divergence_result["percentile"],
            "divergence_level": divergence_result["level"],
            # 资金动向（三窗口百分位）
            "taker_ratio": current_mi.taker_buy_sell_ratio,
            "taker_ratio_change": taker_change["diff"],
            "taker_ratio_pct": taker_pct,
            "flow_1h": flow_1h.net,
            "flow_1h_pct_7d": flow_pct,
            "flow_1h_pct_30d": flow_pct,  # 暂用 7d 数据
            "flow_1h_pct_90d": flow_pct,  # 暂用 7d 数据
            "flow_binance": flow_1h.by_exchange.get("binance", 0),
            # 持仓 & 爆仓
            "oi_value": current_oi.open_interest_usd if current_oi else 0,
            "oi_change_1h": oi_change_1h,
            "oi_change_1h_pct": oi_pct,
            "liq_1h_total": liq_stats.total,
            "liq_long_ratio": liq_long_ratio,
            # 情绪指标
            "funding_rate": indicators.funding_rate if indicators else 0,
            "funding_rate_pct": funding_pct,
            "spot_perp_spread": indicators.spot_perp_spread if indicators else 0,
            "spot_perp_spread_pct": 50,  # 合约溢价暂无历史数据
        }

        # 获取历史统计数据（为所有 P90+ 维度获取历史参考）
        history_data: dict[str, Any] = {}

        # 定义维度映射：(data中的百分位字段, 极端事件中的dimension名)
        dimension_checks = [
            (flow_pct, "flow_1h"),
            (oi_pct, "oi_change_1h"),
            (funding_pct, "funding_rate"),
            (top_pos_pct, "top_position_ratio"),
            (global_acc_pct, "global_account_ratio"),
            (taker_pct, "taker_ratio"),
        ]

        for pct, dimension in dimension_checks:
            if pct >= 90:
                event_summary = await self.event_stats.get_summary(
                    short_symbol, dimension, window_days=7
                )
                latest_event = await self.event_stats.get_latest_event(
                    short_symbol, dimension, window_days=7
                )
                if event_summary["count"] >= 5:
                    history_data[dimension] = {
                        "stats": event_summary["stats"],
                        "latest": latest_event,
                    }

        return format_insight_report_with_history(data, history_data)

    async def _scheduled_report(self) -> None:
        interval = self.config.intervals.report_hours * 3600
        while self.running:
            await asyncio.sleep(interval)
            for symbol in self.config.symbols:
                try:
                    if self.config.insight.enabled:
                        report = await self._generate_insight_report(symbol)
                    else:
                        report = await self._generate_report(symbol)
                    await self.notifier.send_message(report)
                except Exception as e:
                    logger.error(f"Failed to send report for {symbol}: {e}")

    async def _fetch_indicators(self) -> None:
        interval = self.config.intervals.oi_fetch_minutes * 60
        while self.running:
            try:
                # OI 采集
                oi_snapshots = await self.indicator_fetcher.fetch_all_oi()
                for oi in oi_snapshots:
                    await self.db.insert_oi_snapshot(oi)

                # 市场指标采集
                if self.config.insight.enabled:
                    for symbol in self.config.symbols:
                        mi = await self.indicator_fetcher.fetch_market_indicators(symbol)
                        if mi:
                            await self.db.insert_market_indicator(mi)
                            logger.debug(f"Market indicators: {symbol} saved")
            except Exception as e:
                logger.error(f"Failed to fetch indicators: {e}")
            await asyncio.sleep(interval)

    async def _fetch_long_short_ratio(self) -> None:
        """采集多空比数据"""
        interval = self.config.long_short_ratio.fetch_interval_minutes * 60
        while self.running:
            try:
                for symbol in self.config.symbols:
                    ls_indicators = await self.indicator_fetcher.fetch_long_short_indicators(symbol)
                    if ls_indicators:
                        timestamp = int(time.time() * 1000)

                        # 存储 4 种多空比数据（直接使用 API 返回的值）
                        await self.db.insert_long_short_snapshot(
                            symbol=symbol,
                            timestamp=timestamp,
                            ratio_type="global",
                            long_ratio=ls_indicators.global_long,
                            short_ratio=ls_indicators.global_short,
                            long_short_ratio=ls_indicators.global_ratio,
                        )
                        await self.db.insert_long_short_snapshot(
                            symbol=symbol,
                            timestamp=timestamp,
                            ratio_type="top_account",
                            long_ratio=ls_indicators.top_account_long,
                            short_ratio=ls_indicators.top_account_short,
                            long_short_ratio=ls_indicators.top_account_ratio,
                        )
                        await self.db.insert_long_short_snapshot(
                            symbol=symbol,
                            timestamp=timestamp,
                            ratio_type="top_position",
                            long_ratio=ls_indicators.top_position_long,
                            short_ratio=ls_indicators.top_position_short,
                            long_short_ratio=ls_indicators.top_position_ratio,
                        )
                        await self.db.insert_long_short_snapshot(
                            symbol=symbol,
                            timestamp=timestamp,
                            ratio_type="taker",
                            long_ratio=ls_indicators.taker_buy,
                            short_ratio=ls_indicators.taker_sell,
                            long_short_ratio=ls_indicators.taker_ratio,
                        )
                        logger.debug(f"Long short ratio: {symbol} saved")
            except Exception as e:
                logger.error(f"Failed to fetch long short ratio: {e}")
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

    async def _check_insight_alerts(self) -> None:
        """检测市场异动"""
        from src.aggregator.percentile import calculate_percentile

        if not self.config.insight.enabled:
            return

        # 存储上一次的状态
        previous_states: dict[str, dict[str, Any]] = {}
        window_hours = self.config.percentile.window_days * 24

        while self.running:
            await asyncio.sleep(60)  # 每分钟检查

            for symbol in self.config.symbols:
                try:
                    current_mi = await self.db.get_latest_market_indicator(symbol)
                    if not current_mi:
                        continue

                    trades_1h = await self.db.get_trades(symbol, hours=1)
                    flow = calculate_flow(trades_1h)

                    # 计算分歧
                    history_mi = await self.db.get_market_indicator_history(
                        symbol, hours=window_hours
                    )
                    divergence_history = [
                        abs(mi.top_position_ratio - mi.global_account_ratio) for mi in history_mi
                    ]
                    divergence_result = calculate_divergence(
                        current_mi.top_position_ratio,
                        current_mi.global_account_ratio,
                        divergence_history,
                    )

                    # 计算 taker_ratio 百分位
                    taker_history = [mi.taker_buy_sell_ratio for mi in history_mi]
                    taker_pct = calculate_percentile(current_mi.taker_buy_sell_ratio, taker_history)

                    current_state = {
                        "divergence_level": divergence_result["level"],
                        "top_ratio": current_mi.top_position_ratio,
                        "flow_1h": flow.net,
                        "taker_ratio": current_mi.taker_buy_sell_ratio,
                        "taker_ratio_pct": taker_pct,
                    }

                    if symbol in previous_states:
                        alerts = check_insight_alerts(
                            current_state,
                            previous_states[symbol],
                            self.config.insight.alerts.flow_threshold_usd,
                        )

                        for alert in alerts:
                            # 发送异动提醒
                            short_symbol = symbol.split("/")[0]
                            msg = f"⚡ {short_symbol} 市场异动\n\n{alert.message}"
                            await self.notifier.send_message(msg)
                            logger.info(f"Insight alert: {symbol} - {alert.type}")

                    previous_states[symbol] = current_state

                except Exception as e:
                    logger.error(f"Failed to check insight alerts for {symbol}: {e}")

    async def _check_tiered_alerts(self) -> None:
        """检查分级告警（观察/重要提醒）"""
        from src.aggregator.percentile import calculate_percentile

        observe_config = self.config.alerts.observe
        important_config = self.config.alerts.important

        if not observe_config.enabled and not important_config.enabled:
            return

        # 历史数据窗口（天数）
        window_days = self.config.percentile.window_days
        window_hours = window_days * 24

        # 冷却记录：{(symbol, level): last_sent_time}
        last_sent: dict[tuple[str, str], float] = {}

        while self.running:
            await asyncio.sleep(60)  # 每分钟检查

            for symbol in self.config.symbols:
                try:
                    # 获取当前数据
                    trades_1h = await self.db.get_trades(symbol, hours=1)
                    flow = calculate_flow(trades_1h)

                    liqs_1h = await self.db.get_liquidations(symbol, hours=1)
                    liq_stats = calculate_liquidations(liqs_1h)

                    current_oi = await self.db.get_latest_oi(symbol)
                    past_oi_1h = await self.db.get_oi_at(symbol, hours_ago=1)
                    oi_change = calculate_oi_change(current_oi, past_oi_1h)

                    indicators = await self.indicator_fetcher.fetch_indicators(symbol)
                    if not indicators:
                        continue

                    # 获取市场指标（大户/散户持仓）
                    current_mi = await self.db.get_latest_market_indicator(symbol)
                    if not current_mi:
                        continue

                    # 获取历史数据用于计算百分位
                    trades_history = await self.db.get_trades(symbol, hours=window_hours)
                    liqs_history = await self.db.get_liquidations(symbol, hours=window_hours)
                    history_mi = await self.db.get_market_indicator_history(
                        symbol, hours=window_hours
                    )

                    # 按小时聚合历史 flow 数据
                    flow_history: list[float] = []
                    hour_buckets: dict[int, list[float]] = {}
                    for t in trades_history:
                        hour = t.timestamp // 3600000
                        if hour not in hour_buckets:
                            hour_buckets[hour] = []
                        net = t.value_usd if t.side == "buy" else -t.value_usd
                        hour_buckets[hour].append(net)
                    for nets in hour_buckets.values():
                        flow_history.append(abs(sum(nets)))

                    # 按小时聚合历史爆仓数据
                    liq_history: list[float] = []
                    liq_buckets: dict[int, float] = {}
                    for liq in liqs_history:
                        hour = liq.timestamp // 3600000
                        liq_buckets[hour] = liq_buckets.get(hour, 0) + liq.value_usd
                    liq_history = list(liq_buckets.values())

                    # 计算 OI 变化历史（遍历过去 N 小时）
                    oi_change_history: list[float] = []
                    for h in range(1, min(window_hours, 168)):  # 最多 168 小时 (7天)
                        oi_h = await self.db.get_oi_at(symbol, hours_ago=h)
                        oi_h_prev = await self.db.get_oi_at(symbol, hours_ago=h + 1)
                        if oi_h and oi_h_prev and oi_h_prev.open_interest_usd > 0:
                            change = (
                                (oi_h.open_interest_usd - oi_h_prev.open_interest_usd)
                                / oi_h_prev.open_interest_usd
                                * 100
                            )
                            oi_change_history.append(abs(change))

                    # 获取多空比历史
                    ls_history = await self.db.get_long_short_snapshots(
                        symbol, "global", hours=window_hours
                    )
                    ls_ratio_history = [s["long_short_ratio"] for s in ls_history]

                    # 大户/散户持仓历史
                    top_pos_history = [mi.top_position_ratio for mi in history_mi]
                    global_acc_history = [mi.global_account_ratio for mi in history_mi]

                    # 历史数据不足时跳过（需要至少 10 个数据点才能计算有意义的百分位）
                    min_history = 10
                    oi_len, ls_len = len(oi_change_history), len(ls_ratio_history)
                    if oi_len < min_history or ls_len < min_history:
                        logger.debug(f"Skip tiered alerts {symbol}: OI={oi_len} LS={ls_len}")
                        continue

                    # 计算各维度百分位
                    top_pos_pct = calculate_percentile(
                        current_mi.top_position_ratio, top_pos_history
                    )
                    global_acc_pct = calculate_percentile(
                        current_mi.global_account_ratio, global_acc_history
                    )

                    percentiles: dict[str, float] = {
                        "主力资金": calculate_percentile(flow.net, flow_history),
                        "OI变化": calculate_percentile(oi_change, oi_change_history),
                        "爆仓": calculate_percentile(liq_stats.total, liq_history),
                        "资金费率": calculate_percentile(
                            indicators.funding_rate,
                            [-0.01, 0, 0.01, 0.02, 0.03, 0.05],  # 业界标准范围
                        ),
                        "多空比": calculate_percentile(
                            indicators.long_short_ratio, ls_ratio_history
                        ),
                        "大户持仓": top_pos_pct,
                        "散户持仓": global_acc_pct,
                    }

                    # 记录极端事件 (P90+)
                    short_symbol = symbol.split("/")[0]
                    current_price = indicators.futures_price
                    dimension_map = {
                        "主力资金": ("flow_1h", flow.net),
                        "OI变化": ("oi_change_1h", oi_change),
                        "爆仓": ("liq_1h", liq_stats.total),
                        "资金费率": ("funding_rate", indicators.funding_rate),
                        "多空比": ("long_short_ratio", indicators.long_short_ratio),
                        "大户持仓": ("top_position_ratio", current_mi.top_position_ratio),
                        "散户持仓": ("global_account_ratio", current_mi.global_account_ratio),
                    }
                    for dim_name, pct in percentiles.items():
                        if pct >= 90 and dim_name in dimension_map:
                            dim_key, value = dimension_map[dim_name]
                            # 使用配置的窗口记录（实时运行受 retention_days 限制）
                            # 三窗口（7d/30d/90d）在回测脚本 detector.py 中实现
                            await self.extreme_tracker.record_event(
                                symbol=short_symbol,
                                dimension=dim_key,
                                window_days=7,
                                value=value,
                                percentile=pct,
                                price=current_price,
                            )

                    # 检查分级告警
                    threshold = observe_config.percentile_threshold
                    min_dims = important_config.min_dimensions
                    alerts = check_tiered_alerts(percentiles, threshold, min_dims)

                    for alert in alerts:
                        short_symbol = symbol.split("/")[0]
                        now = time.time()

                        # 检查冷却
                        cooldown_key = (symbol, alert.level.value)
                        cooldown_minutes = (
                            observe_config.cooldown_minutes
                            if alert.level == AlertLevel.OBSERVE
                            else important_config.cooldown_minutes
                        )
                        if cooldown_key in last_sent:
                            elapsed = now - last_sent[cooldown_key]
                            if elapsed < cooldown_minutes * 60:
                                logger.debug(
                                    f"Skip {alert.level.value} alert {symbol}: "
                                    f"cooldown {int(elapsed)}s/{cooldown_minutes * 60}s"
                                )
                                continue

                        timestamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

                        # 构建详细数据
                        data = {
                            "symbol": short_symbol,
                            "price": indicators.futures_price if indicators else 0,
                            "price_change_1h": 0,
                            "dimensions": alert.dimensions,
                            "timestamp": timestamp,
                            # 大户/散户详细数据
                            "top_position_ratio": current_mi.top_position_ratio,
                            "top_position_pct": top_pos_pct,
                            "global_account_ratio": current_mi.global_account_ratio,
                            "global_account_pct": global_acc_pct,
                            # 其他指标原始值
                            "flow_net": flow.net,
                            "oi_change": oi_change,
                            "liq_total": liq_stats.total,
                            "funding_rate": indicators.funding_rate,
                        }

                        if alert.level == AlertLevel.OBSERVE and observe_config.enabled:
                            msg = format_observe_alert(data)
                            await self.notifier.send_message(msg)
                            last_sent[cooldown_key] = now
                            logger.info(f"Observe alert: {symbol}")
                        elif alert.level == AlertLevel.IMPORTANT and important_config.enabled:
                            msg = format_important_alert(data)
                            await self.notifier.send_message(msg)
                            last_sent[cooldown_key] = now
                            logger.info(f"Important alert: {symbol}")

                except Exception as e:
                    logger.error(f"Failed to check tiered alerts for {symbol}: {e}")

    async def _check_absolute_alerts(self) -> None:
        """检查绝对阈值告警 (whale_flow, oi_change, liquidation)"""
        from src.aggregator.percentile import calculate_percentile

        whale_config = self.config.alerts.whale_flow
        oi_config = self.config.alerts.oi_change
        liq_config = self.config.alerts.liquidation

        # 如果全部禁用则退出
        if not (whale_config.enabled or oi_config.enabled or liq_config.enabled):
            return

        # 冷却记录：{(symbol, alert_type): last_sent_time}
        last_sent: dict[tuple[str, str], float] = {}
        cooldown_seconds = 30 * 60  # 30 分钟冷却

        window_hours = self.config.percentile.window_days * 24

        while self.running:
            await asyncio.sleep(60)  # 每分钟检查

            for symbol in self.config.symbols:
                try:
                    short_symbol = symbol.split("/")[0]
                    now = time.time()

                    # 获取当前数据
                    trades_1h = await self.db.get_trades(symbol, hours=1)
                    flow = calculate_flow(trades_1h)

                    current_oi = await self.db.get_latest_oi(symbol)
                    past_oi_1h = await self.db.get_oi_at(symbol, hours_ago=1)
                    oi_change = calculate_oi_change(current_oi, past_oi_1h)

                    liqs_1h = await self.db.get_liquidations(symbol, hours=1)
                    liq_stats = calculate_liquidations(liqs_1h)

                    indicators = await self.indicator_fetcher.fetch_indicators(symbol)
                    if not indicators:
                        continue

                    # 获取历史数据用于百分位计算
                    trades_history = await self.db.get_trades(symbol, hours=window_hours)
                    flow_history: list[float] = []
                    hour_buckets: dict[int, list[float]] = {}
                    for t in trades_history:
                        hour = t.timestamp // 3600000
                        if hour not in hour_buckets:
                            hour_buckets[hour] = []
                        net = t.value_usd if t.side == "buy" else -t.value_usd
                        hour_buckets[hour].append(net)
                    for nets in hour_buckets.values():
                        flow_history.append(sum(nets))

                    liqs_history = await self.db.get_liquidations(symbol, hours=window_hours)
                    liq_buckets: dict[int, float] = {}
                    for liq in liqs_history:
                        hour = liq.timestamp // 3600000
                        liq_buckets[hour] = liq_buckets.get(hour, 0) + liq.value_usd
                    liq_history = list(liq_buckets.values())

                    oi_change_history: list[float] = []
                    for h in range(1, min(window_hours, 48)):
                        oi_h = await self.db.get_oi_at(symbol, hours_ago=h)
                        oi_h_prev = await self.db.get_oi_at(symbol, hours_ago=h + 1)
                        if oi_h and oi_h_prev and oi_h_prev.open_interest_usd > 0:
                            change = (
                                (oi_h.open_interest_usd - oi_h_prev.open_interest_usd)
                                / oi_h_prev.open_interest_usd
                                * 100
                            )
                            oi_change_history.append(change)

                    # 计算百分位
                    flow_pct = calculate_percentile(flow.net, flow_history)
                    oi_pct = calculate_percentile(oi_change, oi_change_history)
                    liq_pct = calculate_percentile(liq_stats.total, liq_history)

                    timestamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

                    # 1. 大单流向告警
                    if whale_config.enabled and whale_config.threshold_usd:
                        if abs(flow.net) >= whale_config.threshold_usd:
                            cooldown_key = (symbol, "whale_flow")
                            if cooldown_key not in last_sent or (
                                now - last_sent[cooldown_key] >= cooldown_seconds
                            ):
                                data = {
                                    "symbol": short_symbol,
                                    "price": indicators.futures_price,
                                    "price_change_1h": 0,
                                    "flow_1h": flow.net,
                                    "flow_1h_pct": flow_pct,
                                    "flow_binance": flow.by_exchange.get("binance", 0),
                                    "timestamp": timestamp,
                                }
                                msg = format_whale_alert(data)
                                await self.notifier.send_message(msg)
                                last_sent[cooldown_key] = now
                                logger.info(f"Whale flow alert: {symbol} {flow.net:,.0f}")

                    # 2. OI 变化告警
                    if oi_config.enabled and oi_config.threshold_pct:
                        if abs(oi_change) >= oi_config.threshold_pct:
                            cooldown_key = (symbol, "oi_change")
                            if cooldown_key not in last_sent or (
                                now - last_sent[cooldown_key] >= cooldown_seconds
                            ):
                                data = {
                                    "symbol": short_symbol,
                                    "price": indicators.futures_price,
                                    "price_change_1h": 0,
                                    "oi_change_1h": oi_change,
                                    "oi_change_1h_pct": oi_pct,
                                    "oi_value": current_oi.open_interest_usd if current_oi else 0,
                                    "timestamp": timestamp,
                                }
                                msg = format_oi_alert(data)
                                await self.notifier.send_message(msg)
                                last_sent[cooldown_key] = now
                                logger.info(f"OI change alert: {symbol} {oi_change:+.2f}%")

                    # 3. 爆仓告警
                    if liq_config.enabled and liq_config.threshold_usd:
                        if liq_stats.total >= liq_config.threshold_usd:
                            cooldown_key = (symbol, "liquidation")
                            if cooldown_key not in last_sent or (
                                now - last_sent[cooldown_key] >= cooldown_seconds
                            ):
                                liq_long_ratio = (
                                    liq_stats.long / liq_stats.total if liq_stats.total > 0 else 0.5
                                )
                                data = {
                                    "symbol": short_symbol,
                                    "price": indicators.futures_price,
                                    "price_change_1h": 0,
                                    "liq_1h_total": liq_stats.total,
                                    "liq_1h_pct": liq_pct,
                                    "liq_long_ratio": liq_long_ratio,
                                    "timestamp": timestamp,
                                }
                                msg = format_liquidation_alert(data)
                                await self.notifier.send_message(msg)
                                last_sent[cooldown_key] = now
                                logger.info(f"Liquidation alert: {symbol} {liq_stats.total:,.0f}")

                except Exception as e:
                    logger.error(f"Failed to check absolute alerts for {symbol}: {e}")

    async def _backfill_events(self) -> None:
        """定时回填极端事件的后续价格"""
        while self.running:
            await asyncio.sleep(3600)  # 每小时运行一次
            try:
                filled = await self.event_backfiller.run()
                if filled > 0:
                    logger.info(f"Backfilled {filled} price fields")
            except Exception as e:
                logger.error(f"Failed to backfill events: {e}")

    async def _cleanup_old_data(self) -> None:
        """定时清理过期数据"""
        interval = self.config.intervals.cleanup_hours * 3600
        retention_days = self.config.database.retention_days

        while self.running:
            await asyncio.sleep(interval)
            try:
                deleted = await self.db.cleanup_old_data(retention_days)
                total = sum(deleted.values())
                if total > 0:
                    logger.info(f"Cleaned up {total} old records: {deleted}")
            except Exception as e:
                logger.error(f"Failed to cleanup old data: {e}")

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
            asyncio.create_task(self._fetch_long_short_ratio()),
            asyncio.create_task(self._check_alerts()),
            asyncio.create_task(self._check_insight_alerts()),
            asyncio.create_task(self._check_tiered_alerts()),
            asyncio.create_task(self._check_absolute_alerts()),
            asyncio.create_task(self._backfill_events()),
            asyncio.create_task(self._cleanup_old_data()),
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
        await self.binance_client.close()
        await self.db.close()

        logger.info("Crypto Monitor stopped")


async def main() -> None:
    config = load_config(Path("config.yaml"))
    monitor = CryptoMonitor(config)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
