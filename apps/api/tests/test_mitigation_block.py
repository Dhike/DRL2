from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection, FVGState
from app.scanner.mitigation_block import detect_mitigation_blocks
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


BOS = BreakOfStructure("bullish", 110.0, 4, BASE + timedelta(hours=4))

# Verified by dry run: bullish OB at candle 2 stays clear of its own
# range through candles 3-5, candle 6 wicks back in.
ROWS = [
    (100, 102, 103, 99),
    (102, 104, 105, 101),
    (104, 101, 105, 100),
    (108, 109, 110, 107),
    (109, 115, 116, 108),
    (115, 113, 116, 111),
    (113, 108, 114, 99),
]

ACTIVE_OB = OrderBlock(
    direction=FVGDirection.BULLISH, high_price=105.0, low_price=100.0,
    open_price=104.0, close_price=101.0, midpoint_price=102.5,
    candle_index=2, bos=BOS, state=FVGState.ACTIVE,
)
MITIGATED_OB = OrderBlock(
    direction=FVGDirection.BULLISH, high_price=105.0, low_price=100.0,
    open_price=104.0, close_price=101.0, midpoint_price=102.5,
    candle_index=2, bos=BOS, state=FVGState.MITIGATED,
)


def test_still_active_order_block_is_skipped():
    candles = candles_from(ROWS)
    assert detect_mitigation_blocks(candles, (ACTIVE_OB,)) == ()


def test_mitigated_bullish_order_block_produces_a_mitigation_block():
    candles = candles_from(ROWS)
    blocks = detect_mitigation_blocks(candles, (MITIGATED_OB,))

    assert len(blocks) == 1
    mb = blocks[0]
    assert mb.direction is FVGDirection.BULLISH  # same as the source OB
    assert mb.order_block_candle_index == 2
    assert mb.mitigation_candle_index == 6
    assert (mb.high_price, mb.low_price) == (105.0, 100.0)
    assert mb.order_block is MITIGATED_OB


def test_mitigated_bearish_order_block_produces_a_mitigation_block():
    """Verified by dry run: candles 1-3 all stay below the OB's low
    (95), candle 4's high (96) reaches back into the range."""
    bearish_rows = [
        (96, 99, 100, 95),
        (91, 90, 92, 89),
        (90, 89, 91, 88),
        (89, 88, 90, 87),
        (88, 91, 96, 87),
    ]
    candles = candles_from(bearish_rows)
    bearish_ob = OrderBlock(
        direction=FVGDirection.BEARISH, high_price=100.0, low_price=95.0,
        open_price=96.0, close_price=99.0, midpoint_price=97.5,
        candle_index=0, bos=BOS, state=FVGState.MITIGATED,
    )

    blocks = detect_mitigation_blocks(candles, (bearish_ob,))
    assert len(blocks) == 1
    assert blocks[0].direction is FVGDirection.BEARISH
    assert blocks[0].mitigation_candle_index == 4


def test_no_candles_or_no_order_blocks_returns_nothing():
    candles = candles_from(ROWS)
    assert detect_mitigation_blocks([], (MITIGATED_OB,)) == ()
    assert detect_mitigation_blocks(candles, ()) == ()


def test_multiple_order_blocks_mixed_states():
    candles = candles_from(ROWS)
    result = detect_mitigation_blocks(candles, (ACTIVE_OB, MITIGATED_OB))
    assert len(result) == 1
    assert result[0].order_block is MITIGATED_OB
