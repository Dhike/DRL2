from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection
from app.scanner.rejection_block import detect_rejection_blocks

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candles_from(rows):
    for i, (o, c, h, low) in enumerate(rows):
        assert low <= min(o, c) and h >= max(o, c) and low <= h, f"row {i} invalid"
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=float(o), high=float(h), low=float(low), close=float(c),
            volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


def test_bullish_rejection_at_exact_thresholds():
    """body=5, lower_wick=10 == 2*body and == 0.4*range(25): both
    thresholds met exactly, confirming >= is inclusive."""
    candles = candles_from([(100, 105, 115, 90)])
    blocks = detect_rejection_blocks(candles)

    assert len(blocks) == 1
    b = blocks[0]
    assert b.direction is FVGDirection.BULLISH
    assert b.candle_index == 0
    assert (b.high_price, b.low_price) == (115.0, 90.0)
    assert b.midpoint_price == 102.5


def test_bullish_candle_with_too_small_a_wick_is_not_a_rejection():
    """body=6, lower_wick=2: well under both thresholds."""
    candles = candles_from([(100, 106, 108, 98)])
    assert detect_rejection_blocks(candles) == ()


def test_bearish_rejection_at_exact_thresholds():
    """body=5, upper_wick=10 == 2*body; range=16, 0.4*range=6.4 <= 10."""
    candles = candles_from([(105, 100, 115, 99)])
    blocks = detect_rejection_blocks(candles)

    assert len(blocks) == 1
    b = blocks[0]
    assert b.direction is FVGDirection.BEARISH
    assert (b.high_price, b.low_price) == (115.0, 99.0)


def test_bearish_candle_with_too_small_a_wick_is_not_a_rejection():
    """body=6, upper_wick=2: well under both thresholds."""
    candles = candles_from([(105, 99, 107, 98)])
    assert detect_rejection_blocks(candles) == ()


def test_zero_range_candle_is_skipped():
    candles = candles_from([(100, 100, 100, 100)])
    assert detect_rejection_blocks(candles) == ()


def test_ordinary_full_bodied_candle_is_not_a_rejection():
    """No meaningful wick on either side."""
    candles = candles_from([(100, 110, 110.2, 99.8)])
    assert detect_rejection_blocks(candles) == ()


def test_multiple_candles_each_checked_independently():
    rows = [
        (100, 105, 115, 90),   # 0: bullish rejection (verified above)
        (100, 106, 108, 98),   # 1: not a rejection
        (105, 100, 115, 99),   # 2: bearish rejection (verified above)
    ]
    candles = candles_from(rows)
    blocks = detect_rejection_blocks(candles)

    assert len(blocks) == 2
    assert blocks[0].candle_index == 0
    assert blocks[0].direction is FVGDirection.BULLISH
    assert blocks[1].candle_index == 2
    assert blocks[1].direction is FVGDirection.BEARISH


def test_empty_candle_list_returns_nothing():
    assert detect_rejection_blocks([]) == ()
