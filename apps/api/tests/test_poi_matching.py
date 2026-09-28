from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.balanced_price_range import BalancedPriceRange
from app.scanner.fair_value_gap import FairValueGap, FVGDirection, FVGState
from app.scanner.order_block import OrderBlock
from app.scanner.rejection_block import RejectionBlock
from app.scanner.structure import BreakOfStructure
from app.scanner.poi_matching import (
    average_true_range,
    classify_interaction,
    compute_distance,
    compute_overlap,
    match_poi,
    ob_family_boundaries,
    poi_direction,
    poi_status,
    poi_zone,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candle(open_, high, low, close):
    return Candle(timestamp=BASE, open=open_, high=high, low=low, close=close, volume=1.0)


def make_candles(n, base_price=100.0, step=0.0):
    """n quiet candles of fixed range 5 (for a predictable ATR=5)."""
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=base_price + i * step, high=base_price + i * step + 2.5,
            low=base_price + i * step - 2.5, close=base_price + i * step,
            volume=1.0,
        )
        for i in range(n)
    ]


def test_compute_overlap_true_and_false():
    assert compute_overlap(100, 110, 105, 115) is True
    assert compute_overlap(100, 110, 120, 130) is False
    assert compute_overlap(100, 105, 105, 115) is True  # touching boundary counts


def test_compute_distance_zero_when_overlapping():
    assert compute_distance(100, 110, 105, 115) == 0.0


def test_compute_distance_above_and_below():
    assert compute_distance(100, 110, 115, 120) == 5.0
    assert compute_distance(100, 110, 85, 90) == 10.0


def test_average_true_range_needs_enough_history():
    assert average_true_range(make_candles(10)) is None  # needs period+1=15
    atr = average_true_range(make_candles(20))
    assert atr == 5.0  # fixed range=5 candles -> TR=5 every time


def test_classify_interaction_all_four_levels():
    zone = (100.0, 110.0)
    assert classify_interaction(*zone, candle(120, 130, 120, 125)) == "NONE"
    assert classify_interaction(*zone, candle(112, 115, 108, 113)) == "WICK_TOUCH"
    assert classify_interaction(*zone, candle(105, 109, 104, 107)) == "CLOSED_INSIDE"
    assert classify_interaction(*zone, candle(112, 113, 94, 95)) == "CLOSED_THROUGH"


def test_poi_zone_for_fvg_and_order_block():
    fvg = FairValueGap(
        direction=FVGDirection.BULLISH, lower_price=101, upper_price=111,
        first_candle_index=0, middle_candle_index=1, third_candle_index=2,
    )
    assert poi_zone(fvg) == (101, 111)

    bos = BreakOfStructure("bullish", 110.0, 4, BASE)
    ob = OrderBlock(
        direction=FVGDirection.BULLISH, high_price=105.0, low_price=100.0,
        open_price=104.0, close_price=101.0, midpoint_price=102.5,
        candle_index=2, bos=bos,
    )
    assert poi_zone(ob) == (100.0, 105.0)


def test_poi_direction_none_for_bpr():
    bullish = FairValueGap(FVGDirection.BULLISH, 100, 110, 0, 1, 2)
    bearish = FairValueGap(FVGDirection.BEARISH, 105, 115, 3, 4, 5)
    bpr = BalancedPriceRange(105, 110, bullish, bearish)
    assert poi_direction(bpr) is None
    assert poi_direction(bullish) is FVGDirection.BULLISH


def test_poi_status_defaults_to_active_for_rejection_block():
    rb = RejectionBlock(
        direction=FVGDirection.BULLISH, high_price=105, low_price=100,
        open_price=101, close_price=104, midpoint_price=102.5, candle_index=0,
    )
    assert poi_status(rb) is FVGState.ACTIVE


def test_ob_family_boundaries_bullish_uses_low_as_invalidation():
    bos = BreakOfStructure("bullish", 110.0, 4, BASE)
    ob = OrderBlock(
        direction=FVGDirection.BULLISH, high_price=105.0, low_price=100.0,
        open_price=104.0, close_price=101.0, midpoint_price=102.5,
        candle_index=2, bos=bos,
    )
    body_low, body_high, invalidation = ob_family_boundaries(ob)
    assert (body_low, body_high) == (101.0, 104.0)  # min/max(open, close)
    assert invalidation == 100.0  # low_price, the wick extreme


def test_ob_family_boundaries_none_for_non_ob_types():
    fvg = FairValueGap(FVGDirection.BULLISH, 100, 110, 0, 1, 2)
    assert ob_family_boundaries(fvg) is None


def test_match_poi_returns_none_for_inverted_status():
    fvg = FairValueGap(FVGDirection.BULLISH, 100, 110, 0, 1, 2, state=FVGState.INVERTED)
    candles = make_candles(20)
    assert match_poi(fvg, candles, 19, "RETEST") is None


def test_match_poi_mitigated_status_still_matches():
    fvg = FairValueGap(FVGDirection.BULLISH, 100, 110, 0, 1, 2, state=FVGState.MITIGATED)
    candles = make_candles(20, base_price=105.0)  # candle 19 near [100,110]
    result = match_poi(fvg, candles, 19, "RETEST")
    assert result is not None
    assert result.status is FVGState.MITIGATED


def test_match_poi_reports_overlap_near_and_interaction_together():
    fvg = FairValueGap(FVGDirection.BULLISH, 100, 110, 0, 1, 2)
    candles = make_candles(19, base_price=200.0)  # far away, big ATR-irrelevant history
    candles.append(candle(105, 109, 104, 107))  # index 19: inside the zone
    result = match_poi(fvg, candles, 19, "CONFIRMATION")

    assert result.overlap is True
    assert result.near is True  # overlap implies near
    assert result.interaction == "CLOSED_INSIDE"
    assert result.match_context == "CONFIRMATION"
    assert result.poi_type == "FairValueGap"


def test_match_poi_distant_poi_is_not_near():
    fvg = FairValueGap(FVGDirection.BULLISH, 100, 110, 0, 1, 2)
    candles = make_candles(20, base_price=100.0)  # ATR=5
    far_candle = candle(300, 305, 295, 300)  # distance far beyond 0.25*ATR=1.25
    candles.append(far_candle)
    result = match_poi(fvg, candles, 20, "RETEST")

    assert result.overlap is False
    assert result.near is False
    assert result.interaction == "NONE"


def test_match_poi_near_without_overlap_uses_atr_threshold():
    """ATR is computed EXCLUDING the reference candle itself (the last
    14 of the 20 flat quiet candles, all TR=5), so ATR=5 exactly."""
    fvg = FairValueGap(FVGDirection.BULLISH, 100, 110, 0, 1, 2)
    candles = make_candles(20, base_price=100.0)  # ATR=5, excluding index 20
    close_candle = candle(112, 113, 111, 112)
    candles.append(close_candle)
    result = match_poi(fvg, candles, 20, "RETEST")

    assert result.overlap is False
    assert result.near is True
    assert result.distance_atr == 0.2
