from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection, FVGState
from app.scanner.vacuum_block import (
    detect_vacuum_block_mitigation,
    detect_vacuum_blocks,
)

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


# Verified by dry run: 10 quiet candles, then a strong bullish
# displacement whose low (102.5) gaps above candle 9's high (101.5).
BULLISH_QUIET = [
    (100 + i * 0.1, 100.1 + i * 0.1, 100.6 + i * 0.1, 99.6 + i * 0.1) for i in range(10)
]
BULLISH_DISPLACEMENT = (103, 110, 111, 102.5)
BULLISH_ROWS = BULLISH_QUIET + [BULLISH_DISPLACEMENT]

# Verified by dry run: 10 quiet candles, then a strong bearish
# displacement whose high (97.5) gaps below candle 9's low (98.5).
BEARISH_QUIET = [
    (100 - i * 0.1, 99.9 - i * 0.1, 100.6 - i * 0.1, 99.4 - i * 0.1) for i in range(10)
]
BEARISH_DISPLACEMENT = (97, 90, 97.5, 89)
BEARISH_ROWS = BEARISH_QUIET + [BEARISH_DISPLACEMENT]


def test_bullish_vacuum_block_from_strong_displacement():
    candles = candles_from(BULLISH_ROWS)
    blocks = detect_vacuum_blocks(candles)

    assert len(blocks) == 1
    vb = blocks[0]
    assert vb.direction is FVGDirection.BULLISH
    assert vb.previous_candle_index == 9
    assert vb.displacement_candle_index == 10
    assert (vb.high_price, vb.low_price) == (102.5, 101.5)
    assert vb.state is FVGState.ACTIVE
    assert vb.mitigation_candle_index is None


def test_bearish_vacuum_block_from_strong_displacement():
    candles = candles_from(BEARISH_ROWS)
    blocks = detect_vacuum_blocks(candles)

    assert len(blocks) == 1
    vb = blocks[0]
    assert vb.direction is FVGDirection.BEARISH
    assert (vb.high_price, vb.low_price) == (98.5, 97.5)


def test_needs_at_least_eleven_candles():
    assert detect_vacuum_blocks(candles_from(BULLISH_ROWS[:10])) == ()
    assert detect_vacuum_blocks([]) == ()


def test_a_weak_displacement_candle_does_not_qualify():
    """Same quiet lead-in, but the final candle's body is too small
    relative to both its own range and the preceding average."""
    weak_displacement = (100.9, 101.1, 101.5, 100.6)  # small body, no gap either
    rows = BULLISH_QUIET + [weak_displacement]
    assert detect_vacuum_blocks(candles_from(rows)) == ()


def test_a_strong_candle_without_a_gap_does_not_qualify():
    """Strong body, but the previous candle's high is NOT below the
    displacement's low -- no genuine price inefficiency."""
    no_gap_displacement = (100.9, 108, 109, 100.4)  # low=100.4, below candle9 high=101.5
    rows = BULLISH_QUIET + [no_gap_displacement]
    assert detect_vacuum_blocks(candles_from(rows)) == ()


def test_vacuum_block_stays_active_until_mitigated():
    not_yet_candle = (110, 112, 113, 109)
    mitigation_candle = (112, 108, 113, 101.8)
    rows = BULLISH_ROWS + [not_yet_candle, mitigation_candle]
    candles = candles_from(rows)

    vb = detect_vacuum_blocks(candles)[0]

    before = detect_vacuum_block_mitigation(candles[:12], vb)
    assert before.state is FVGState.ACTIVE
    assert before.mitigation_candle_index is None

    after = detect_vacuum_block_mitigation(candles, vb)
    assert after.state is FVGState.MITIGATED
    assert after.mitigation_candle_index == 12


def test_mitigation_is_a_noop_on_an_already_resolved_block():
    from dataclasses import replace

    candles = candles_from(BULLISH_ROWS)
    vb = detect_vacuum_blocks(candles)[0]
    already_mitigated = replace(vb, state=FVGState.MITIGATED, mitigation_candle_index=5)

    result = detect_vacuum_block_mitigation(candles, already_mitigated)
    assert result is already_mitigated
