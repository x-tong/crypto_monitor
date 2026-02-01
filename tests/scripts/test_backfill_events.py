# tests/scripts/test_backfill_events.py


def test_parse_args():
    from src.scripts.backfill_events import parse_args

    args = parse_args(["--days", "365", "--symbol", "BTC"])
    assert args.days == 365
    assert args.symbol == "BTC"


def test_parse_args_defaults():
    from src.scripts.backfill_events import parse_args

    args = parse_args([])
    assert args.days == 365
    assert args.symbol is None  # 默认处理所有 symbol


def test_parse_args_all_options():
    from src.scripts.backfill_events import parse_args

    args = parse_args(["--days", "180", "--symbol", "BTC", "--skip-download"])
    assert args.days == 180
    assert args.symbol == "BTC"
    assert args.skip_download is True


def test_parse_args_download_only():
    from src.scripts.backfill_events import parse_args

    args = parse_args(["--download-only"])
    assert args.download_only is True
