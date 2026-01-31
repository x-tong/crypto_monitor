# tests/storage/test_models.py


def test_market_indicator_creation():
    from src.storage.models import MarketIndicator

    indicator = MarketIndicator(
        id=None,
        symbol="BTC/USDT:USDT",
        timestamp=1706600000000,
        top_account_ratio=1.5,
        top_position_ratio=1.6,
        global_account_ratio=0.9,
        taker_buy_sell_ratio=1.1,
    )
    assert indicator.symbol == "BTC/USDT:USDT"
    assert indicator.top_account_ratio == 1.5
