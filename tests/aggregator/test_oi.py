# tests/aggregator/test_oi.py
from src.aggregator.oi import calculate_oi_change, interpret_oi_price
from src.storage.models import OISnapshot


def test_calculate_oi_change():
    current = OISnapshot(1, "binance", "BTC/USDT:USDT", 1706600000000, 50000, 5000000000)
    past = OISnapshot(2, "binance", "BTC/USDT:USDT", 1706596400000, 48000, 4800000000)

    change = calculate_oi_change(current, past)

    # (5000000000 - 4800000000) / 4800000000 * 100 = 4.166...%
    assert abs(change - 4.1667) < 0.01


def test_calculate_oi_change_none():
    assert calculate_oi_change(None, None) == 0.0
    current = OISnapshot(1, "binance", "BTC/USDT:USDT", 1706600000000, 50000, 5000000000)
    assert calculate_oi_change(current, None) == 0.0


def test_interpret_oi_price_new_long():
    assert interpret_oi_price(oi_change=2.0, price_change=1.5) == "新多入场"


def test_interpret_oi_price_new_short():
    assert interpret_oi_price(oi_change=2.0, price_change=-1.5) == "新空入场"


def test_interpret_oi_price_short_close():
    assert interpret_oi_price(oi_change=-2.0, price_change=1.5) == "空头平仓"


def test_interpret_oi_price_long_close():
    assert interpret_oi_price(oi_change=-2.0, price_change=-1.5) == "多头平仓"


def test_interpret_oi_price_stable():
    assert interpret_oi_price(oi_change=0.5, price_change=0.5) == "持仓稳定"
