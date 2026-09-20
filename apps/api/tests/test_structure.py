from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.structure import (
    MarketState,
    StructureLabel,
    StructureScope,
    SwingPoint,
    SwingType,
    analyze_market_structure,
    classify_market_state,
    classify_swings,
    detect_confirmed_swings,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
HIGH, LOW = SwingType.HIGH, SwingType.LOW
HH, HL, LH, LL = (
    StructureLabel.HH,
    StructureLabel.HL,
    StructureLabel.LH,
    StructureLabel.LL,
)


def candles_from_hl(highs, lows):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=(high + low) / 2,
            high=float(high),
            low=float(low),
            close=(high + low) / 2,
            volume=1.0,
        )
        for i, (high, low) in enumerate(zip(highs, lows))
    ]


def candles_from_prices(prices):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=price,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=1.0,
        )
        for i, price in enumerate(prices)
    ]


def swing(index, price, kind, label=None):
    return SwingPoint(
        index=index,
        timestamp=BASE + timedelta(hours=index),
        price=price,
        swing_type=kind,
        label=label,
    )


def labeled(labels):
    return [
        swing(i, 100.0 + i, HIGH if label in (HH, LH) else LOW, label)
        for i, label in enumerate(labels)
    ]


def summary(swings):
    return [(s.index, s.swing_type, s.price, s.label) for s in swings]


# Five-candle-per-leg zigzag, checked index by index: peaks at 4, 12, 20 and
# troughs at 8, 16, 24; every other candle has a higher or lower neighbour
# within two bars, so no accidental swings.
UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]
DOWN_PRICES = [240.0 - price for price in UP_PRICES]


# ---- detect_confirmed_swings -------------------------------------------------


def test_detects_swing_high():
    candles = candles_from_hl([10, 11, 15, 12, 11], [9, 10, 13, 11, 10])
    swings = detect_confirmed_swings(candles)
    assert summary(swings) == [(2, HIGH, 15.0, None)]
    assert swings[0].timestamp == candles[2].timestamp


def test_detects_swing_low():
    candles = candles_from_hl([15, 14, 12, 13, 14], [14, 13, 9, 12, 13])
    assert summary(detect_confirmed_swings(candles)) == [(2, LOW, 9.0, None)]


def test_needs_minimum_candles():
    candles = candles_from_hl([10, 11, 15, 12], [9, 10, 13, 11])
    assert detect_confirmed_swings(candles) == []


def test_equal_highs_are_not_a_swing():
    candles = candles_from_hl([10, 11, 15, 15, 11], [9, 10, 13, 13, 10])
    assert detect_confirmed_swings(candles) == []


def test_peak_in_last_two_candles_is_not_confirmed():
    candles = candles_from_hl(
        [10, 11, 12, 13, 14, 20], [8, 9, 10, 11, 12, 18]
    )
    assert detect_confirmed_swings(candles) == []


def test_swing_is_confirmed_once_two_candles_follow():
    candles = candles_from_hl(
        [10, 11, 12, 15, 12, 11], [8, 9, 10, 13, 10, 9]
    )
    assert summary(detect_confirmed_swings(candles)) == [(3, HIGH, 15.0, None)]


def test_outside_bar_gives_high_then_low():
    candles = candles_from_hl([10, 11, 20, 11, 10], [8, 9, 1, 9, 8])
    assert summary(detect_confirmed_swings(candles)) == [
        (2, HIGH, 20.0, None),
        (2, LOW, 1.0, None),
    ]


def test_custom_bar_counts():
    candles = candles_from_hl([10, 15, 11], [9, 13, 10])
    assert summary(detect_confirmed_swings(candles, 1, 1)) == [
        (1, HIGH, 15.0, None)
    ]
    assert detect_confirmed_swings(candles) == []


# ---- classify_swings ---------------------------------------------------------


def test_labels_follow_previous_high_and_low():
    swings = [
        swing(0, 100.0, HIGH),
        swing(1, 90.0, LOW),
        swing(2, 110.0, HIGH),
        swing(3, 95.0, LOW),
        swing(4, 105.0, HIGH),
        swing(5, 85.0, LOW),
    ]
    labels = [s.label for s in classify_swings(swings)]
    assert labels == [HH, HL, HH, HL, LH, LL]


def test_equal_prices_take_the_weaker_label():
    highs = classify_swings([swing(0, 100.0, HIGH), swing(1, 100.0, HIGH)])
    lows = classify_swings([swing(0, 90.0, LOW), swing(1, 90.0, LOW)])
    assert [s.label for s in highs] == [HH, LH]
    assert [s.label for s in lows] == [HL, LL]


def test_classify_keeps_swing_data_and_leaves_scope_undefined():
    original = [swing(3, 100.0, HIGH), swing(7, 90.0, LOW)]
    result = classify_swings(original)
    assert [(s.index, s.timestamp, s.price, s.swing_type) for s in result] == [
        (s.index, s.timestamp, s.price, s.swing_type) for s in original
    ]
    assert all(s.scope is StructureScope.UNDEFINED for s in result)
    assert all(s.label is None for s in original)


# ---- classify_market_state ---------------------------------------------------


@pytest.mark.parametrize(
    "swings",
    [
        labeled([HH, HL, HH]),
        labeled([HH, HL, HH]) + [swing(9, 1.0, HIGH), swing(10, 2.0, LOW)],
    ],
)
def test_undefined_with_fewer_than_four_labeled_swings(swings):
    assert classify_market_state(swings) is MarketState.UNDEFINED


def test_uptrend():
    assert classify_market_state(labeled([HH, HL, HH, HL])) is MarketState.UPTREND


def test_downtrend():
    assert classify_market_state(labeled([LH, LL, LH, LL])) is MarketState.DOWNTREND


@pytest.mark.parametrize(
    "labels",
    [
        [HH, LL, HH, LL],
        [HH, HL, HH, LH, LL, LH],
    ],
)
def test_balanced_swings_are_ranging(labels):
    assert classify_market_state(labeled(labels)) is MarketState.RANGING


def test_only_the_last_six_swings_count():
    labels = [LH, LL, LH, LL, HH, HL, HH, HL]
    assert classify_market_state(labeled(labels)) is MarketState.UPTREND


def test_three_bullish_of_four_is_an_uptrend():
    assert classify_market_state(labeled([HH, HL, HH, LH])) is MarketState.UPTREND


# ---- analyze_market_structure ------------------------------------------------


def test_uptrend_structure():
    result = analyze_market_structure(candles_from_prices(UP_PRICES))
    assert summary(result.swings) == [
        (4, HIGH, 111.0, HH),
        (8, LOW, 103.0, HL),
        (12, HIGH, 117.0, HH),
        (16, LOW, 107.0, HL),
        (20, HIGH, 123.0, HH),
        (24, LOW, 111.0, HL),
    ]
    assert result.state is MarketState.UPTREND
    assert isinstance(result.swings, tuple)


def test_downtrend_structure():
    result = analyze_market_structure(candles_from_prices(DOWN_PRICES))
    assert summary(result.swings) == [
        (4, LOW, 129.0, HL),
        (8, HIGH, 137.0, HH),
        (12, LOW, 123.0, LL),
        (16, HIGH, 133.0, LH),
        (20, LOW, 117.0, LL),
        (24, HIGH, 129.0, LH),
    ]
    assert result.state is MarketState.DOWNTREND


def test_too_few_candles_is_undefined():
    result = analyze_market_structure(candles_from_prices([100, 101, 102]))
    assert result.state is MarketState.UNDEFINED
    assert result.swings == ()


def test_downtrend_value_is_spelled_correctly():
    assert MarketState.DOWNTREND.value == "downtrend"
