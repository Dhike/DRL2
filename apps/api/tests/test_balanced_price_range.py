from datetime import datetime, timedelta, timezone

from app.scanner.balanced_price_range import detect_bprs, get_fvg_role
from app.scanner.fair_value_gap import FairValueGap, FVGDirection, FVGState

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
BULLISH, BEARISH = FVGDirection.BULLISH, FVGDirection.BEARISH
ACTIVE, MITIGATED, INVERTED = FVGState.ACTIVE, FVGState.MITIGATED, FVGState.INVERTED


def make_fvg(direction, lower, upper, first, third, state=ACTIVE):
    return FairValueGap(
        direction=direction,
        lower_price=lower,
        upper_price=upper,
        first_candle_index=first,
        middle_candle_index=first + 1,
        third_candle_index=third,
        state=state,
    )


def test_overlapping_opposite_direction_gaps_form_a_bpr():
    # bullish [100,110], bearish [105,115] -> overlap [105,110]
    bullish = make_fvg(BULLISH, 100, 110, 0, 2)
    bearish = make_fvg(BEARISH, 105, 115, 3, 5)

    bprs = detect_bprs((bullish, bearish))

    assert len(bprs) == 1
    bpr = bprs[0]
    assert (bpr.lower_price, bpr.upper_price) == (105, 110)
    assert bpr.bullish_fvg is bullish
    assert bpr.bearish_fvg is bearish


def test_order_in_the_input_does_not_affect_the_result():
    bullish = make_fvg(BULLISH, 100, 110, 0, 2)
    bearish = make_fvg(BEARISH, 105, 115, 3, 5)

    bprs = detect_bprs((bearish, bullish))  # bearish listed first

    assert len(bprs) == 1
    bpr = bprs[0]
    assert (bpr.lower_price, bpr.upper_price) == (105, 110)
    assert bpr.bullish_fvg is bullish
    assert bpr.bearish_fvg is bearish


def test_same_direction_pair_is_skipped():
    a = make_fvg(BULLISH, 100, 110, 0, 2)
    b = make_fvg(BULLISH, 105, 115, 3, 5)
    assert detect_bprs((a, b)) == ()


def test_non_overlapping_ranges_are_skipped():
    # bullish [100,105], bearish [110,120] -> lower=110 >= upper=105
    bullish = make_fvg(BULLISH, 100, 105, 0, 2)
    bearish = make_fvg(BEARISH, 110, 120, 3, 5)
    assert detect_bprs((bullish, bearish)) == ()


def test_touching_but_not_overlapping_ranges_are_skipped():
    # lower == upper exactly: strict inequality required
    bullish = make_fvg(BULLISH, 100, 105, 0, 2)
    bearish = make_fvg(BEARISH, 105, 115, 3, 5)
    assert detect_bprs((bullish, bearish)) == ()


def test_same_third_candle_index_pair_is_skipped():
    """Two contradictory readings of the same triplet should never form
    a BPR with each other."""
    bullish = make_fvg(BULLISH, 100, 110, 0, 2)
    bearish = make_fvg(BEARISH, 105, 115, 0, 2)  # same third_candle_index
    assert detect_bprs((bullish, bearish)) == ()


def test_multiple_gaps_can_form_multiple_bprs():
    a = make_fvg(BULLISH, 100, 110, 0, 2)
    b = make_fvg(BEARISH, 105, 115, 3, 5)
    c = make_fvg(BEARISH, 108, 112, 6, 8)

    bprs = detect_bprs((a, b, c))
    assert len(bprs) == 2
    pairs = {(bpr.bullish_fvg, bpr.bearish_fvg) for bpr in bprs}
    assert (a, b) in pairs
    assert (a, c) in pairs


def test_get_fvg_role_active_bullish():
    fvg = make_fvg(BULLISH, 100, 110, 0, 2, state=ACTIVE)
    assert get_fvg_role(fvg) is BULLISH


def test_get_fvg_role_mitigated_keeps_original_direction():
    fvg = make_fvg(BEARISH, 100, 110, 0, 2, state=MITIGATED)
    assert get_fvg_role(fvg) is BEARISH


def test_get_fvg_role_inverted_bullish_becomes_bearish():
    fvg = make_fvg(BULLISH, 100, 110, 0, 2, state=INVERTED)
    assert get_fvg_role(fvg) is BEARISH


def test_get_fvg_role_inverted_bearish_becomes_bullish():
    fvg = make_fvg(BEARISH, 100, 110, 0, 2, state=INVERTED)
    assert get_fvg_role(fvg) is BULLISH
