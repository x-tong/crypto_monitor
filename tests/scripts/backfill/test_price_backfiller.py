# tests/scripts/backfill/test_price_backfiller.py


def test_load_klines(tmp_path):
    from src.scripts.backfill.price_backfiller import load_klines

    # 创建测试 K 线 CSV
    csv_path = tmp_path / "klines.csv"
    # Binance klines CSV 格式: open_time,open,high,low,close,volume,close_time,...
    csv_path.write_text(
        "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
        "1704067200000,42000.0,42500.0,41800.0,42200.0,1000.0,1704070799999,42000000.0,5000,500.0,21000000.0,0\n"
        "1704070800000,42200.0,42800.0,42100.0,42600.0,1200.0,1704074399999,50400000.0,6000,600.0,25200000.0,0\n"
    )

    klines = load_klines([csv_path])

    assert len(klines) == 2
    assert klines[1704067200000] == 42200.0  # close price
    assert klines[1704070800000] == 42600.0


def test_backfill_prices():
    from src.scripts.backfill.price_backfiller import backfill_prices

    # K 线数据：每小时一个价格
    klines = {
        1704067200000: 42000.0,  # hour 0
        1704070800000: 42100.0,  # hour 1
        1704074400000: 42200.0,  # hour 2
        1704078000000: 42300.0,  # hour 3
        1704081600000: 42400.0,  # hour 4
        1704085200000: 42500.0,  # hour 5 (4h later)
        1704110400000: 42800.0,  # hour 12
        1704153600000: 43200.0,  # hour 24
        1704240000000: 43500.0,  # hour 48
    }

    event = {
        "triggered_at": 1704067200000,  # hour 0
        "value": 1000000.0,
    }

    backfilled = backfill_prices(event, klines)

    assert backfilled["price_at_trigger"] == 42000.0
    assert backfilled["price_4h"] == 42400.0
    assert backfilled["price_12h"] == 42800.0
    assert backfilled["price_24h"] == 43200.0
    assert backfilled["price_48h"] == 43500.0
