# tests/scripts/backfill/test_processor.py

import pytest


def test_calculate_monthly_p95_threshold(tmp_path):
    from src.scripts.backfill.processor import calculate_monthly_p95_threshold

    # 创建测试 CSV
    csv_path = tmp_path / "test.csv"
    # aggTrades CSV 格式
    csv_path.write_text(
        "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
        "1,50000.0,0.1,1,1,1704067200000,True\n"  # $5,000
        "2,50000.0,0.2,2,2,1704067260000,False\n"  # $10,000
        "3,50000.0,1.0,3,3,1704067320000,True\n"  # $50,000
        "4,50000.0,2.0,4,4,1704067380000,False\n"  # $100,000
        "5,50000.0,5.0,5,5,1704067440000,True\n"  # $250,000
    )

    threshold = calculate_monthly_p95_threshold(csv_path)

    # P95 应该接近最大值
    assert threshold > 50000
    assert threshold <= 250000


def test_process_agg_trades_to_flow(tmp_path):
    from src.scripts.backfill.processor import process_agg_trades_to_flow

    csv_path = tmp_path / "test.csv"
    csv_path.write_text(
        "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
        "1,50000.0,3.0,1,1,1704067200000,True\n"  # sell $150,000 @ hour 0
        "2,50000.0,2.0,2,2,1704067260000,False\n"  # buy $100,000 @ hour 0
        "3,50000.0,4.0,3,3,1704070800000,False\n"  # buy $200,000 @ hour 1
    )

    # 阈值 $50,000，所有交易都算大单
    flow = process_agg_trades_to_flow(csv_path, threshold=50000)

    # 返回 {timestamp_hour: net_flow}
    assert len(flow) == 2
    # Hour 0: buy $100,000 - sell $150,000 = -$50,000
    assert flow[1704067200000] == pytest.approx(-50000, rel=0.01)
    # Hour 1: buy $200,000 = +$200,000
    assert flow[1704070800000] == pytest.approx(200000, rel=0.01)
