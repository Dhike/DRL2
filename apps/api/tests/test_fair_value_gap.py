from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.fair_value_gap import (
    FVGDirection,
    FVGState,
    detect_fair_value_gaps,
    detect_fvg_inversion,
    detect_fvg_mitigation,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candles_from(rows):
    """Each row is (open, close, high, low)."""
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


def find_gap(gaps, first_index, third_index):
    return next(
        g for g in gaps
        if g.first_candle_index == first_index and g.third_candle_index == third_index
    )


# Verified by dry run: candle 2 gaps clean above candle 0 (a real FVG),
# stays flat through 3-4 (no premature mitigation), then candle 5 wicks
# back into the gap (mitigation) and candle 6 closes below it (inversion).
# Later candles inevitably form their OWN additional overlapping gaps
# against this sustained move -- that is a real property of the rule
# (confirmed by dry run across several fixture attempts), not a defect,
# so tests target this specific gap by its indices rather than assert a
# fixed total gap count.
BULLISH_ROWS = [
    (100, 100, 101, 99),
    (100, 100, 101, 99),
    (112, 112, 113, 111),
    (112, 112, 113, 111.5),
    (112, 112, 113, 111.5),
    (110, 109, 111, 108),
    (105, 95, 106, 94),
]

BEARISH_ROWS = [
    (100, 100, 101, 99),
    (100, 100, 101, 99),
    (88, 88, 89, 87),
    (87, 87, 88.5, 86),
    (87, 87, 88.5, 86),
    (90, 91, 92, 89),
    (91, 92, 93, 90),
]


def test_detects_a_clean_bullish_gap():
    candles = candles_from(BULLISH_ROWS)
    gaps = detect_fair_value_gaps(candles)
    gap = find_gap(gaps, 0, 2)

    assert gap.direction is FVGDirection.BULLISH
    assert (gap.lower_price, gap.upper_price) == (101.0, 111.0)
    assert gap.middle_candle_index == 1
    assert gap.state is FVGState.ACTIVE


def test_detects_a_clean_bearish_gap():
    candles = candles_from(BEARISH_ROWS)
    gaps = detect_fair_value_gaps(candles)
    gap = find_gap(gaps, 0, 2)

    assert gap.direction is FVGDirection.BEARISH
    assert (gap.lower_price, gap.upper_price) == (89.0, 99.0)
    assert gap.state is FVGState.ACTIVE


def test_too_few_candles_returns_nothing():
    assert detect_fair_value_gaps(candles_from(BULLISH_ROWS[:2])) == ()
    assert detect_fair_value_gaps([]) == ()


def test_bullish_gap_stays_active_while_flat():
    """Candles 3-4 stay above the gap's upper price; no premature
    mitigation should be reported for a snapshot ending there."""
    candles = candles_from(BULLISH_ROWS[:5])
    gap = find_gap(detect_fair_value_gaps(candles), 0, 2)
    result = detect_fvg_mitigation(candles, gap)
    assert result.state is FVGState.ACTIVE


def test_bullish_gap_gets_mitigated_then_inverted():
    candles = candles_from(BULLISH_ROWS)
    gap = find_gap(detect_fair_value_gaps(candles), 0, 2)

    mitigated = detect_fvg_mitigation(candles, gap)
    assert mitigated.state is FVGState.MITIGATED

    inverted = detect_fvg_inversion(candles, mitigated)
    assert inverted.state is FVGState.INVERTED


def test_bearish_gap_gets_mitigated_but_not_inverted():
    candles = candles_from(BEARISH_ROWS)
    gap = find_gap(detect_fair_value_gaps(candles), 0, 2)

    mitigated = detect_fvg_mitigation(candles, gap)
    assert mitigated.state is FVGState.MITIGATED

    still_mitigated = detect_fvg_inversion(candles, mitigated)
    assert still_mitigated.state is FVGState.MITIGATED


def test_mitigation_is_a_noop_on_an_already_resolved_gap():
    from dataclasses import replace

    candles = candles_from(BULLISH_ROWS)
    gap = find_gap(detect_fair_value_gaps(candles), 0, 2)
    already_inverted = replace(gap, state=FVGState.INVERTED)

    result = detect_fvg_mitigation(candles, already_inverted)
    assert result is already_inverted


def test_inversion_is_a_noop_on_an_active_gap():
    candles = candles_from(BULLISH_ROWS[:5])  # never reaches mitigation
    gap = find_gap(detect_fair_value_gaps(candles), 0, 2)

    result = detect_fvg_inversion(candles, gap)
    assert result is gap
