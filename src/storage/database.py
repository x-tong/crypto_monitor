# src/storage/database.py
import time

import aiosqlite

from .models import Liquidation, MarketIndicator, OISnapshot, PriceAlert, Trade


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
