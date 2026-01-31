# src/notifier/telegram.py
import logging
import re
from collections.abc import Callable, Coroutine
from typing import Any

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
        self.app: Application | None = None  # type: ignore[type-arg]

        # Callbacks
        self.on_watch: Callable[[str, float], Coroutine[Any, Any, None]] | None = None
        self.on_unwatch: Callable[[str, float], Coroutine[Any, Any, None]] | None = None
        self.on_list: Callable[[], Coroutine[Any, Any, str]] | None = None
        self.on_report: Callable[[str], Coroutine[Any, Any, str]] | None = None
        self.on_status: Callable[[], Coroutine[Any, Any, str]] | None = None

    async def send_message(self, text: str) -> None:
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode="HTML",
        )

    @staticmethod
    def _parse_watch_command(text: str) -> tuple[str, float] | None:
        match = re.match(r"/(?:un)?watch\s+(\w+)\s+([\d.]+)", text)
        if match:
            return match.group(1).upper(), float(match.group(2))
        return None

    async def _handle_watch(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        result = self._parse_watch_command(update.message.text)
        if not result:
            await update.message.reply_text("用法: /watch BTC 100000")
            return

        symbol, price = result
        if self.on_watch:
            await self.on_watch(symbol, price)
        await update.message.reply_text(f"✅ 已添加 {symbol} {int(price)} 监控")

    async def _handle_unwatch(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        result = self._parse_watch_command(update.message.text)
        if not result:
            await update.message.reply_text("用法: /unwatch BTC 100000")
            return

        symbol, price = result
        if self.on_unwatch:
            await self.on_unwatch(symbol, price)
        await update.message.reply_text(f"✅ 已取消 {symbol} {int(price)} 监控")

    async def _handle_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return

        if self.on_list:
            text = await self.on_list()
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("暂无监控价位")

    async def _handle_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        parts = update.message.text.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"

        if self.on_report:
            text = await self.on_report(symbol)
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("报告生成中...")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return

        if self.on_status:
            text = await self.on_status()
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("系统运行中")

    def setup_handlers(self, app: Application) -> None:  # type: ignore[type-arg]
        app.add_handler(CommandHandler("watch", self._handle_watch))
        app.add_handler(CommandHandler("unwatch", self._handle_unwatch))
        app.add_handler(CommandHandler("list", self._handle_list))
        app.add_handler(CommandHandler("report", self._handle_report))
        app.add_handler(CommandHandler("status", self._handle_status))

    async def start_polling(self) -> None:
        self.app = Application.builder().token(self.bot_token).build()
        self.setup_handlers(self.app)
        await self.app.initialize()
        await self.app.start()
        if self.app.updater:
            await self.app.updater.start_polling()

    async def stop_polling(self) -> None:
        if self.app:
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
