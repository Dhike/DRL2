from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.breaker_block import detect_breaker_blocks
from app.scanner.fair_value_gap import FVGDirection, FVGState
from app.scanner.order_block import OrderBlock
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


BOS = BreakOfStructure("bearish", 100.0, 5, BASE + timedelta(hours=5))

# Verified by dry run: candle 2's wick touches the boundary but its
# CLOSE doesn't cross it (no invalidation); candle 3's close does.
BEARISH_OB_ROWS = [
    (104, 101, 105, 100),
    (101, 103, 104, 100),
    (103, 104, 106, 102),
    (104, 107, 108, 103),
]
BEARISH_OB = OrderBlock(
    direction=FVGDirection.BEARISH, high_price=105.0, low_price=100.0,
    open_price=104.0, close_price=101.0, midpoint_price=102.5,
    candle_index=0, bos=BOS, state=FVGState.ACTIVE,
)

BULLISH_OB_ROWS = [
    (96, 99, 100, 95),
    (99, 98, 100, 96),
    (98, 96, 99, 93),
    (96, 92, 97, 90),
]
BULLISH_OB = OrderBlock(
    direction=FVGDirection.BULLISH, high_price=100.0, low_price=95.0,
    open_price=96.0, close_price=99.0, midpoint_price=97.5,
    candle_index=0, bos=BOS, state=FVGState.ACTIVE,
)


def test_bearish_order_block_invalidated_becomes_a_bullish_breaker():
    candles = candles_from(BEARISH_OB_ROWS)
    breakers = detect_breaker_blocks(candles, (BEARISH_OB,))

    assert len(breakers) == 1
    breaker = breakers[0]
    assert breaker.direction is FVGDirection.BULLISH
    assert breaker.invalidation_candle_index == 3
    assert breaker.order_block_candle_index == 0
    assert (breaker.high_price, breaker.low_price) == (105.0, 100.0)
    assert breaker.order_block is BEARISH_OB


def test_bullish_order_block_invalidated_becomes_a_bearish_breaker():
    candles = candles_from(BULLISH_OB_ROWS)
    breakers = detect_breaker_blocks(candles, (BULLISH_OB,))

    assert len(breakers) == 1
    breaker = breakers[0]
    assert breaker.direction is FVGDirection.BEARISH
    assert breaker.invalidation_candle_index == 3
    assert (breaker.high_price, breaker.low_price) == (100.0, 95.0)


def test_a_wick_through_the_boundary_without_a_close_does_not_invalidate():
    """Candle 2 in both fixtures wicks through the boundary but closes
    back inside -- a snapshot ending there must show no invalidation."""
    bearish_snapshot = candles_from(BEARISH_OB_ROWS[:3])
    assert detect_breaker_blocks(bearish_snapshot, (BEARISH_OB,)) == ()

    bullish_snapshot = candles_from(BULLISH_OB_ROWS[:3])
    assert detect_breaker_blocks(bullish_snapshot, (BULLISH_OB,)) == ()


def test_no_candles_or_no_order_blocks_returns_nothing():
    candles = candles_from(BEARISH_OB_ROWS)
    assert detect_breaker_blocks([], (BEARISH_OB,)) == ()
    assert detect_breaker_blocks(candles, ()) == ()


def test_multiple_order_blocks_each_get_their_own_breaker_check():
    candles = candles_from(BEARISH_OB_ROWS)
    # A second order block that never gets invalidated in this candle
    # range (its low is far below anything reached).
    unaffected_ob = OrderBlock(
        direction=FVGDirection.BULLISH, high_price=50.0, low_price=45.0,
        open_price=46.0, close_price=49.0, midpoint_price=47.5,
        candle_index=0, bos=BOS, state=FVGState.ACTIVE,
    )
    breakers = detect_breaker_blocks(candles, (BEARISH_OB, unaffected_ob))
    assert len(breakers) == 1
    assert breakers[0].order_block is BEARISH_OB
