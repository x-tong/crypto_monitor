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


def test_extreme_event_model():
    from src.storage.models import ExtremeEvent

    event = ExtremeEvent(
        id=None,
        symbol="BTC",
        dimension="flow_1h",
        window_days=30,
        triggered_at=1706600000000,
        value=47_700_000.0,
        percentile=92.5,
        price_at_trigger=82000.0,
        price_4h=None,
        price_12h=None,
        price_24h=None,
        price_48h=None,
    )
    assert event.symbol == "BTC"
    assert event.window_days == 30
    assert event.price_4h is None
