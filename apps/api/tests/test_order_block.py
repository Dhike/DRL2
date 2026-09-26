from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection, FVGState
from app.scanner.order_block import detect_order_block_mitigation, detect_order_blocks
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


# Verified by dry run: candle 2 (bearish) is the nearest opposite-color
# candle before the bullish BOS at candle 4; candles 3-5 stay clear of
# its [100,105] range (no premature mitigation), candle 6 wicks back in.
BULLISH_ROWS = [
    (100, 102, 103, 99),
    (102, 104, 105, 101),
    (104, 101, 105, 100),   # the order block candle
    (108, 109, 110, 107),
    (109, 115, 116, 108),   # BOS displacement candle
    (115, 113, 116, 111),
    (113, 108, 114, 99),    # mitigation candle
]
BULLISH_BOS = BreakOfStructure("bullish", 110.0, 4, BASE + timedelta(hours=4))


def test_bullish_order_block_is_the_nearest_bearish_candle_before_the_bos():
    candles = candles_from(BULLISH_ROWS)
    blocks = detect_order_blocks(candles, (BULLISH_BOS,))

    assert len(blocks) == 1
    ob = blocks[0]
    assert ob.direction is FVGDirection.BULLISH
    assert ob.candle_index == 2
    assert (ob.high_price, ob.low_price) == (105.0, 100.0)
    assert (ob.open_price, ob.close_price) == (104.0, 101.0)
    assert ob.midpoint_price == 102.5
    assert ob.bos is BULLISH_BOS
    assert ob.state is FVGState.ACTIVE


def test_bearish_order_block_is_the_nearest_bullish_candle_before_the_bos():
    rows = [
        (100, 98, 101, 97),
        (98, 96, 99, 95),
        (96, 99, 100, 95),      # the order block candle (bullish)
        (99, 97, 100, 96),
        (97, 90, 98, 89),       # BOS displacement candle
    ]
    bos = BreakOfStructure("bearish", 95.0, 4, BASE + timedelta(hours=4))
    candles = candles_from(rows)

    blocks = detect_order_blocks(candles, (bos,))
    assert len(blocks) == 1
    ob = blocks[0]
    assert ob.direction is FVGDirection.BEARISH
    assert ob.candle_index == 2
    assert (ob.high_price, ob.low_price) == (100.0, 95.0)


def test_bos_at_or_before_index_zero_is_skipped():
    candles = candles_from(BULLISH_ROWS)
    bos_at_zero = BreakOfStructure("bullish", 100.0, 0, BASE)
    assert detect_order_blocks(candles, (bos_at_zero,)) == ()


def test_bos_beyond_the_candle_list_is_skipped():
    candles = candles_from(BULLISH_ROWS)
    bos_out_of_range = BreakOfStructure(
        "bullish", 100.0, len(candles), BASE + timedelta(hours=len(candles))
    )
    assert detect_order_blocks(candles, (bos_out_of_range,)) == ()


def test_no_candles_or_no_bos_returns_nothing():
    assert detect_order_blocks([], (BULLISH_BOS,)) == ()
    assert detect_order_blocks(candles_from(BULLISH_ROWS), ()) == ()


def test_order_block_stays_active_while_price_avoids_its_range():
    candles = candles_from(BULLISH_ROWS[:6])  # through candle 5, no mitigation yet
    ob = detect_order_blocks(candles, (BULLISH_BOS,))[0]

    result = detect_order_block_mitigation(candles, ob)
    assert result.state is FVGState.ACTIVE


def test_order_block_gets_mitigated_when_price_returns():
    candles = candles_from(BULLISH_ROWS)
    ob = detect_order_blocks(candles, (BULLISH_BOS,))[0]

    result = detect_order_block_mitigation(candles, ob)
    assert result.state is FVGState.MITIGATED


def test_mitigation_is_a_noop_on_an_already_mitigated_block():
    from dataclasses import replace

    candles = candles_from(BULLISH_ROWS)
    ob = detect_order_blocks(candles, (BULLISH_BOS,))[0]
    already_mitigated = replace(ob, state=FVGState.MITIGATED)

    result = detect_order_block_mitigation(candles, already_mitigated)
    assert result is already_mitigated
