# tests/notifier/test_telegram.py
from unittest.mock import AsyncMock, MagicMock, patch


async def test_send_message():
    with patch("src.notifier.telegram.Bot") as MockBot:
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        MockBot.return_value = mock_bot

        from src.notifier.telegram import TelegramNotifier

        notifier = TelegramNotifier(bot_token="test", chat_id="123")
        await notifier.send_message("Hello")

        mock_bot.send_message.assert_called_once_with(
            chat_id="123",
            text="Hello",
            parse_mode="HTML",
        )


def test_parse_watch_command():
    from src.notifier.telegram import TelegramNotifier

    result = TelegramNotifier._parse_watch_command("/watch BTC 100000")
    assert result == ("BTC", 100000.0)

    result = TelegramNotifier._parse_watch_command("/watch ETH 3500.5")
    assert result == ("ETH", 3500.5)

    result = TelegramNotifier._parse_watch_command("/watch invalid")
    assert result is None
