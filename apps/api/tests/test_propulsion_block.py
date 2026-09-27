from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection, FVGState
from app.scanner.order_block import OrderBlock
from app.scanner.propulsion_block import detect_propulsion_blocks
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


BULLISH_BOS = BreakOfStructure("bullish", 110.0, 10, BASE + timedelta(hours=10))
BEARISH_BOS = BreakOfStructure("bearish", 90.0, 10, BASE + timedelta(hours=10))

# Verified by dry run: interaction at candle 3, confirmation at candle 6.
BULLISH_ROWS = [
    (96, 99, 100, 95),
    (105, 107, 108, 104),
    (106, 108, 109, 105),
    (100.5, 99, 101, 98),
    (98, 97, 99, 96),
    (97, 96, 98, 95.5),
    (96, 103, 104, 95),
]
BULLISH_OB = OrderBlock(
    direction=FVGDirection.BULLISH, high_price=100.0, low_price=95.0,
    open_price=96.0, close_price=99.0, midpoint_price=97.5,
    candle_index=0, bos=BULLISH_BOS, state=FVGState.ACTIVE,
)

BEARISH_ROWS = [
    (104, 101, 105, 100),
    (95, 93, 96, 92),
    (94, 92, 95, 91),
    (99.5, 101, 102, 99),
    (102, 103, 104, 101),
    (103, 104, 105, 102),
    (104, 97, 105, 96),
]
BEARISH_OB = OrderBlock(
    direction=FVGDirection.BEARISH, high_price=105.0, low_price=100.0,
    open_price=104.0, close_price=101.0, midpoint_price=102.5,
    candle_index=0, bos=BEARISH_BOS, state=FVGState.ACTIVE,
)


def test_bullish_order_block_retested_then_confirmed():
    candles = candles_from(BULLISH_ROWS)
    result = detect_propulsion_blocks(candles, (BULLISH_OB,))

    assert len(result) == 1
    p = result[0]
    assert p.direction is FVGDirection.BULLISH  # unchanged from the OB
    assert p.order_block_candle_index == 0
    assert p.interaction_candle_index == 3
    assert p.confirmation_candle_index == 6
    assert (p.high_price, p.low_price) == (100.0, 95.0)
    assert p.order_block is BULLISH_OB


def test_bearish_order_block_retested_then_confirmed():
    candles = candles_from(BEARISH_ROWS)
    result = detect_propulsion_blocks(candles, (BEARISH_OB,))

    assert len(result) == 1
    p = result[0]
    assert p.direction is FVGDirection.BEARISH  # unchanged from the OB
    assert p.interaction_candle_index == 3
    assert p.confirmation_candle_index == 6


def test_no_confirmation_yet_before_the_confirmation_candle():
    candles = candles_from(BULLISH_ROWS[:6])  # through candle 5, no confirmation
    assert detect_propulsion_blocks(candles, (BULLISH_OB,)) == ()


def test_no_interaction_means_confirmation_is_never_checked():
    candles = candles_from(BULLISH_ROWS[:3])  # never overlaps the OB
    assert detect_propulsion_blocks(candles, (BULLISH_OB,)) == ()


def test_no_candles_or_no_order_blocks_returns_nothing():
    candles = candles_from(BULLISH_ROWS)
    assert detect_propulsion_blocks([], (BULLISH_OB,)) == ()
    assert detect_propulsion_blocks(candles, ()) == ()


def test_multiple_order_blocks_each_checked_independently():
    candles = candles_from(BULLISH_ROWS)
    unaffected_ob = OrderBlock(
        direction=FVGDirection.BEARISH, high_price=50.0, low_price=45.0,
        open_price=46.0, close_price=49.0, midpoint_price=47.5,
        candle_index=0, bos=BULLISH_BOS, state=FVGState.ACTIVE,
    )
    result = detect_propulsion_blocks(candles, (BULLISH_OB, unaffected_ob))
    assert len(result) == 1
    assert result[0].order_block is BULLISH_OB
