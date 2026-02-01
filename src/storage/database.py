# src/storage/database.py
import time
from typing import Any

import aiosqlite

from .models import (
    ExtremeEvent,
    Liquidation,
    MarketIndicator,
    OISnapshot,
    PriceAlert,
    Trade,
)


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        await self._create_tables()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def _create_tables(self) -> None:
        assert self.conn is not None
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                side TEXT NOT NULL,
                value_usd REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, timestamp);

            CREATE TABLE IF NOT EXISTS liquidations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                value_usd REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_liq_symbol_time ON liquidations(symbol, timestamp);

            CREATE TABLE IF NOT EXISTS oi_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open_interest REAL NOT NULL,
                open_interest_usd REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON oi_snapshots(symbol, timestamp);

            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                last_position TEXT,
                last_triggered_at INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_price_alerts_symbol ON price_alerts(symbol);

            CREATE TABLE IF NOT EXISTS thresholds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                p95_value REAL NOT NULL,
                sample_count INTEGER NOT NULL,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS market_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                top_account_ratio REAL NOT NULL,
                top_position_ratio REAL NOT NULL,
                global_account_ratio REAL NOT NULL,
                taker_buy_sell_ratio REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_mi_symbol_time ON market_indicators(symbol, timestamp);

            CREATE TABLE IF NOT EXISTS long_short_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                ratio_type TEXT NOT NULL,
                long_ratio REAL NOT NULL,
                short_ratio REAL NOT NULL,
                long_short_ratio REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_ls_symbol_type_time
                ON long_short_snapshots(symbol, ratio_type, timestamp);

            CREATE TABLE IF NOT EXISTS extreme_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                dimension TEXT NOT NULL,
                window_days INTEGER NOT NULL,
                triggered_at INTEGER NOT NULL,
                value REAL NOT NULL,
                percentile REAL NOT NULL,
                price_at_trigger REAL NOT NULL,
                price_4h REAL,
                price_12h REAL,
                price_24h REAL,
                price_48h REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_extreme_events_lookup
                ON extreme_events(symbol, dimension, window_days, triggered_at);
        """)
        await self.conn.commit()

    async def insert_trade(self, trade: Trade) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO trades (exchange, symbol, timestamp, price, amount, side, value_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.exchange,
                trade.symbol,
                trade.timestamp,
                trade.price,
                trade.amount,
                trade.side,
                trade.value_usd,
            ),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_trades(self, symbol: str, hours: int) -> list[Trade]:
        assert self.conn is not None
        cutoff = int(time.time() * 1000) - hours * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT id, exchange, symbol, timestamp, price, amount, side, value_usd
               FROM trades WHERE symbol = ? AND timestamp >= ?
               ORDER BY timestamp DESC""",
            (symbol, cutoff),
        )
        rows = await cursor.fetchall()
        return [Trade(*row) for row in rows]

    async def insert_price_alert(self, alert: PriceAlert) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO price_alerts (symbol, price, last_position, last_triggered_at)
               VALUES (?, ?, ?, ?)""",
            (alert.symbol, alert.price, alert.last_position, alert.last_triggered_at),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_price_alerts(self, symbol: str) -> list[PriceAlert]:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """SELECT id, symbol, price, last_position, last_triggered_at
               FROM price_alerts WHERE symbol = ?""",
            (symbol,),
        )
        rows = await cursor.fetchall()
        return [PriceAlert(*row) for row in rows]

    async def delete_price_alert(self, symbol: str, price: float) -> None:
        assert self.conn is not None
        await self.conn.execute(
            "DELETE FROM price_alerts WHERE symbol = ? AND price = ?",
            (symbol, price),
        )
        await self.conn.commit()

    async def update_price_alert(
        self, alert_id: int, position: str | None = None, triggered_at: int | None = None
    ) -> None:
        assert self.conn is not None
        updates = []
        params: list[str | int] = []
        if position is not None:
            updates.append("last_position = ?")
            params.append(position)
        if triggered_at is not None:
            updates.append("last_triggered_at = ?")
            params.append(triggered_at)
        if updates:
            params.append(alert_id)
            await self.conn.execute(
                f"UPDATE price_alerts SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            await self.conn.commit()

    async def insert_liquidation(self, liq: Liquidation) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO liquidations
               (exchange, symbol, timestamp, side, price, quantity, value_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                liq.exchange,
                liq.symbol,
                liq.timestamp,
                liq.side,
                liq.price,
                liq.quantity,
                liq.value_usd,
            ),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_liquidations(self, symbol: str, hours: int) -> list[Liquidation]:
        assert self.conn is not None
        cutoff = int(time.time() * 1000) - hours * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT id, exchange, symbol, timestamp, side, price, quantity, value_usd
               FROM liquidations WHERE symbol = ? AND timestamp >= ?
               ORDER BY timestamp DESC""",
            (symbol, cutoff),
        )
        rows = await cursor.fetchall()
        return [Liquidation(*row) for row in rows]

    async def insert_oi_snapshot(self, oi: OISnapshot) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO oi_snapshots
               (exchange, symbol, timestamp, open_interest, open_interest_usd)
               VALUES (?, ?, ?, ?, ?)""",
            (oi.exchange, oi.symbol, oi.timestamp, oi.open_interest, oi.open_interest_usd),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_latest_oi(self, symbol: str) -> OISnapshot | None:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """SELECT id, exchange, symbol, timestamp, open_interest, open_interest_usd
               FROM oi_snapshots WHERE symbol = ?
               ORDER BY timestamp DESC LIMIT 1""",
            (symbol,),
        )
        row = await cursor.fetchone()
        return OISnapshot(*row) if row else None

    async def get_oi_at(self, symbol: str, hours_ago: int) -> OISnapshot | None:
        assert self.conn is not None
        target = int(time.time() * 1000) - hours_ago * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT id, exchange, symbol, timestamp, open_interest, open_interest_usd
               FROM oi_snapshots WHERE symbol = ? AND timestamp <= ?
               ORDER BY timestamp DESC LIMIT 1""",
            (symbol, target),
        )
        row = await cursor.fetchone()
        return OISnapshot(*row) if row else None

    async def insert_market_indicator(self, mi: MarketIndicator) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO market_indicators
               (symbol, timestamp, top_account_ratio, top_position_ratio,
                global_account_ratio, taker_buy_sell_ratio)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                mi.symbol,
                mi.timestamp,
                mi.top_account_ratio,
                mi.top_position_ratio,
                mi.global_account_ratio,
                mi.taker_buy_sell_ratio,
            ),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_latest_market_indicator(self, symbol: str) -> MarketIndicator | None:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """SELECT id, symbol, timestamp, top_account_ratio, top_position_ratio,
                      global_account_ratio, taker_buy_sell_ratio
               FROM market_indicators WHERE symbol = ?
               ORDER BY timestamp DESC LIMIT 1""",
            (symbol,),
        )
        row = await cursor.fetchone()
        return MarketIndicator(*row) if row else None

    async def get_market_indicator_history(self, symbol: str, hours: int) -> list[MarketIndicator]:
        assert self.conn is not None
        cutoff = int(time.time() * 1000) - hours * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT id, symbol, timestamp, top_account_ratio, top_position_ratio,
                      global_account_ratio, taker_buy_sell_ratio
               FROM market_indicators WHERE symbol = ? AND timestamp >= ?
               ORDER BY timestamp DESC""",
            (symbol, cutoff),
        )
        rows = await cursor.fetchall()
        return [MarketIndicator(*row) for row in rows]

    async def insert_long_short_snapshot(
        self,
        symbol: str,
        timestamp: int,
        ratio_type: str,
        long_ratio: float,
        short_ratio: float,
        long_short_ratio: float,
    ) -> int:
        """插入多空比快照"""
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO long_short_snapshots
               (symbol, timestamp, ratio_type, long_ratio, short_ratio, long_short_ratio)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol, timestamp, ratio_type, long_ratio, short_ratio, long_short_ratio),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_long_short_snapshots(
        self,
        symbol: str,
        ratio_type: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """获取多空比快照历史"""
        assert self.conn is not None
        cutoff = int(time.time() * 1000) - hours * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT id, symbol, timestamp, ratio_type, long_ratio, short_ratio, long_short_ratio
               FROM long_short_snapshots
               WHERE symbol = ? AND ratio_type = ? AND timestamp >= ?
               ORDER BY timestamp ASC""",
            (symbol, ratio_type, cutoff),
        )
        rows = await cursor.fetchall()
        columns = [
            "id",
            "symbol",
            "timestamp",
            "ratio_type",
            "long_ratio",
            "short_ratio",
            "long_short_ratio",
        ]
        return [dict(zip(columns, row)) for row in rows]

    async def get_latest_long_short_snapshot(
        self,
        symbol: str,
        ratio_type: str,
    ) -> dict[str, Any] | None:
        """获取最新多空比快照"""
        assert self.conn is not None
        cursor = await self.conn.execute(
            """SELECT id, symbol, timestamp, ratio_type, long_ratio, short_ratio, long_short_ratio
               FROM long_short_snapshots
               WHERE symbol = ? AND ratio_type = ?
               ORDER BY timestamp DESC
               LIMIT 1""",
            (symbol, ratio_type),
        )
        row = await cursor.fetchone()
        if row:
            columns = [
                "id",
                "symbol",
                "timestamp",
                "ratio_type",
                "long_ratio",
                "short_ratio",
                "long_short_ratio",
            ]
            return dict(zip(columns, row))
        return None

    async def insert_extreme_event(self, event: ExtremeEvent) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """INSERT INTO extreme_events
               (symbol, dimension, window_days, triggered_at, value, percentile,
                price_at_trigger, price_4h, price_12h, price_24h, price_48h)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.symbol,
                event.dimension,
                event.window_days,
                event.triggered_at,
                event.value,
                event.percentile,
                event.price_at_trigger,
                event.price_4h,
                event.price_12h,
                event.price_24h,
                event.price_48h,
            ),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_extreme_events(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
        limit: int = 20,
        completed_only: bool = False,
    ) -> list[ExtremeEvent]:
        assert self.conn is not None
        query = """SELECT id, symbol, dimension, window_days, triggered_at, value,
                          percentile, price_at_trigger, price_4h, price_12h, price_24h, price_48h
                   FROM extreme_events
                   WHERE symbol = ? AND dimension = ? AND window_days = ?"""
        if completed_only:
            query += " AND price_48h IS NOT NULL"
        query += " ORDER BY triggered_at DESC LIMIT ?"
        cursor = await self.conn.execute(query, (symbol, dimension, window_days, limit))
        rows = await cursor.fetchall()
        return [ExtremeEvent(*row) for row in rows]

    async def update_extreme_event_price(
        self, event_id: int, price_field: str, price: float
    ) -> None:
        assert self.conn is not None
        valid_fields = {"price_4h", "price_12h", "price_24h", "price_48h"}
        if price_field not in valid_fields:
            raise ValueError(f"Invalid price field: {price_field}")
        await self.conn.execute(
            f"UPDATE extreme_events SET {price_field} = ? WHERE id = ?",
            (price, event_id),
        )
        await self.conn.commit()

    async def get_pending_backfill_events(self) -> list[ExtremeEvent]:
        """获取需要回填后续价格的事件"""
        assert self.conn is not None
        now = int(time.time() * 1000)
        cursor = await self.conn.execute(
            """SELECT id, symbol, dimension, window_days, triggered_at, value,
                      percentile, price_at_trigger, price_4h, price_12h, price_24h, price_48h
               FROM extreme_events
               WHERE (price_4h IS NULL AND triggered_at <= ?)
                  OR (price_12h IS NULL AND triggered_at <= ?)
                  OR (price_24h IS NULL AND triggered_at <= ?)
                  OR (price_48h IS NULL AND triggered_at <= ?)
               ORDER BY triggered_at ASC""",
            (
                now - 4 * 3600 * 1000,
                now - 12 * 3600 * 1000,
                now - 24 * 3600 * 1000,
                now - 48 * 3600 * 1000,
            ),
        )
        rows = await cursor.fetchall()
        return [ExtremeEvent(*row) for row in rows]

    async def is_in_cooldown(
        self,
        symbol: str,
        dimension: str,
        window_days: int,
        cooldown_hours: int = 1,
    ) -> bool:
        """检查是否在冷却期内"""
        assert self.conn is not None
        cutoff = int(time.time() * 1000) - cooldown_hours * 3600 * 1000
        cursor = await self.conn.execute(
            """SELECT 1 FROM extreme_events
               WHERE symbol = ? AND dimension = ? AND window_days = ? AND triggered_at > ?
               LIMIT 1""",
            (symbol, dimension, window_days, cutoff),
        )
        row = await cursor.fetchone()
        return row is not None
