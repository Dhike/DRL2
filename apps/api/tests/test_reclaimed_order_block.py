from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection, FVGState
from app.scanner.order_block import OrderBlock
from app.scanner.reclaimed_order_block import detect_reclaimed_order_blocks
from app.scanner.structure import BreakOfStructure

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


BEARISH_BOS = BreakOfStructure("bearish", 100.0, 10, BASE + timedelta(hours=10))
BULLISH_BOS = BreakOfStructure("bullish", 110.0, 10, BASE + timedelta(hours=10))

# Verified by dry run: invalidation at candle 3, reclaim at candle 6.
BEARISH_OB_ROWS = [
    (104, 101, 105, 100),
    (101, 103, 104, 100),
    (103, 104, 106, 102),
    (104, 107, 108, 103),
    (107, 109, 110, 106),
    (109, 111, 112, 108),
    (111, 103, 112, 102),
]
BEARISH_OB = OrderBlock(
    direction=FVGDirection.BEARISH, high_price=105.0, low_price=100.0,
    open_price=104.0, close_price=101.0, midpoint_price=102.5,
    candle_index=0, bos=BEARISH_BOS, state=FVGState.ACTIVE,
)

BULLISH_OB_ROWS = [
    (96, 99, 100, 95),
    (99, 98, 100, 96),
    (98, 96, 99, 93),
    (96, 92, 97, 90),
    (92, 90, 93, 88),
    (90, 88, 91, 86),
    (88, 97, 98, 87),
]
BULLISH_OB = OrderBlock(
    direction=FVGDirection.BULLISH, high_price=100.0, low_price=95.0,
    open_price=96.0, close_price=99.0, midpoint_price=97.5,
    candle_index=0, bos=BULLISH_BOS, state=FVGState.ACTIVE,
)


def test_bearish_order_block_invalidated_then_reclaimed_becomes_bullish():
    candles = candles_from(BEARISH_OB_ROWS)
    result = detect_reclaimed_order_blocks(candles, (BEARISH_OB,))

    assert len(result) == 1
    r = result[0]
    assert r.direction is FVGDirection.BULLISH
    assert r.order_block_candle_index == 0
    assert r.invalidation_candle_index == 3
    assert r.reclaim_candle_index == 6
    assert (r.high_price, r.low_price) == (105.0, 100.0)
    assert r.order_block is BEARISH_OB


def test_bullish_order_block_invalidated_then_reclaimed_becomes_bearish():
    candles = candles_from(BULLISH_OB_ROWS)
    result = detect_reclaimed_order_blocks(candles, (BULLISH_OB,))

    assert len(result) == 1
    r = result[0]
    assert r.direction is FVGDirection.BEARISH
    assert r.invalidation_candle_index == 3
    assert r.reclaim_candle_index == 6


def test_no_reclaim_yet_before_the_reclaim_candle():
    candles = candles_from(BEARISH_OB_ROWS[:6])  # through candle 5, no reclaim
    assert detect_reclaimed_order_blocks(candles, (BEARISH_OB,)) == ()


def test_no_invalidation_means_no_reclaim_is_ever_checked():
    candles = candles_from(BEARISH_OB_ROWS[:3])  # never invalidates
    assert detect_reclaimed_order_blocks(candles, (BEARISH_OB,)) == ()


def test_no_candles_or_no_order_blocks_returns_nothing():
    candles = candles_from(BEARISH_OB_ROWS)
    assert detect_reclaimed_order_blocks([], (BEARISH_OB,)) == ()
    assert detect_reclaimed_order_blocks(candles, ()) == ()


def test_multiple_order_blocks_each_checked_independently():
    candles = candles_from(BEARISH_OB_ROWS)
    unaffected_ob = OrderBlock(
        direction=FVGDirection.BULLISH, high_price=50.0, low_price=45.0,
        open_price=46.0, close_price=49.0, midpoint_price=47.5,
        candle_index=0, bos=BEARISH_BOS, state=FVGState.ACTIVE,
    )
    result = detect_reclaimed_order_blocks(candles, (BEARISH_OB, unaffected_ob))
    assert len(result) == 1
    assert result[0].order_block is BEARISH_OB
