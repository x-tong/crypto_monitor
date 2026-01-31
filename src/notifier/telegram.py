# src/notifier/telegram.py
import logging
import re
from collections.abc import Callable, Coroutine
from typing import Any

from telegram import Bot, BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """
🔔 <b>Crypto Monitor</b> - BTC/ETH 永续合约监控

<b>功能：</b>
• 大单资金流向追踪
• 持仓量(OI)变化监控
• 爆仓数据聚合
• 关键价位突破提醒
• 定时市场报告

输入 /help 查看所有命令
"""

HELP_MESSAGE = """
📖 <b>命令列表</b>

<b>📊 市场数据</b>
/report [BTC|ETH] - 获取市场报告
/status - 查看系统状态

<b>🔔 价位提醒</b>
/watch BTC 100000 - 添加价位监控
/unwatch BTC 100000 - 取消价位监控
/list - 查看所有监控价位

<b>💡 示例</b>
• /report BTC - BTC 市场报告
• /watch ETH 2500 - ETH 跌破/突破 2500 时提醒
"""

BOT_COMMANDS = [
    BotCommand("start", "开始使用"),
    BotCommand("help", "查看帮助"),
    BotCommand("report", "获取市场报告"),
    BotCommand("status", "系统状态"),
    BotCommand("watch", "添加价位监控"),
    BotCommand("unwatch", "取消价位监控"),
    BotCommand("list", "查看监控列表"),
]


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

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        await update.message.reply_text(WELCOME_MESSAGE, parse_mode="HTML")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        await update.message.reply_text(HELP_MESSAGE, parse_mode="HTML")

    def setup_handlers(self, app: Application) -> None:  # type: ignore[type-arg]
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("help", self._handle_help))
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

        # Set bot command menu
        await self.bot.set_my_commands(BOT_COMMANDS)

        if self.app.updater:
            await self.app.updater.start_polling()

    async def stop_polling(self) -> None:
        if self.app:
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
