from datetime import datetime, timedelta, timezone

import pytest

from app.scanner.structure import (
    BreakOfStructure,
    ExternalStructure,
    MarketState,
    SwingPoint,
    SwingType,
    find_external_structure,
    should_promote_to_external,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
HIGH, LOW = SwingType.HIGH, SwingType.LOW


def swing(index, price, kind):
    return SwingPoint(
        index=index,
        timestamp=BASE + timedelta(hours=index),
        price=float(price),
        swing_type=kind,
        label=None,
    )


def bos(direction, level, candle_index):
    return BreakOfStructure(
        direction=direction,
        broken_level=float(level),
        candle_index=candle_index,
        candle_timestamp=BASE + timedelta(hours=candle_index),
    )


def structure(direction, external_high=None, external_low=None):
    return ExternalStructure(
        direction=direction,
        protected_high=None,
        protected_low=None,
        external_high=external_high,
        external_low=external_low,
    )


# Swings ordered by index: low 95, high 110, low 100, high 105.
L2, H4, L6, H8 = swing(2, 95, LOW), swing(4, 110, HIGH), swing(6, 100, LOW), swing(8, 105, HIGH)
UP_SWINGS = [L2, H4, L6, H8]

# Swings ordered by index: high 120, low 100, high 110, low 105.
H2, L4, H6, L8 = swing(2, 120, HIGH), swing(4, 100, LOW), swing(6, 110, HIGH), swing(8, 105, LOW)
DOWN_SWINGS = [H2, L4, H6, L8]


# ---- find_external_structure -------------------------------------------------


@pytest.mark.parametrize(
    "swings, events, state",
    [
        ([], [bos("bullish", 110, 5)], MarketState.UNDEFINED),
        ([swing(2, 110, HIGH)], [], MarketState.UPTREND),
    ],
)
def test_without_swings_or_breaks_the_structure_is_empty(swings, events, state):
    assert find_external_structure(swings, events, state) == ExternalStructure(
        direction=state,
        protected_high=None,
        protected_low=None,
        external_high=None,
        external_low=None,
    )


def test_bullish_break_gives_uptrend_anchors():
    result = find_external_structure(
        UP_SWINGS, [bos("bullish", 110, 7)], MarketState.RANGING
    )
    assert result == ExternalStructure(
        direction=MarketState.UPTREND,
        protected_high=None,
        protected_low=L6,
        external_high=H4,
        external_low=None,
    )


def test_protected_low_must_be_strictly_before_the_breaking_candle():
    result = find_external_structure(
        UP_SWINGS, [bos("bullish", 110, 6)], MarketState.RANGING
    )
    assert result.protected_low == L2
    assert result.external_high == H4


def test_bearish_break_gives_downtrend_anchors():
    result = find_external_structure(
        DOWN_SWINGS, [bos("bearish", 100, 7)], MarketState.RANGING
    )
    assert result == ExternalStructure(
        direction=MarketState.DOWNTREND,
        protected_high=H6,
        protected_low=None,
        external_high=None,
        external_low=L4,
    )


def test_broken_level_not_found_leaves_the_external_anchor_empty():
    result = find_external_structure(
        UP_SWINGS, [bos("bullish", 999, 7)], MarketState.RANGING
    )
    assert result == ExternalStructure(
        direction=MarketState.UPTREND,
        protected_high=None,
        protected_low=L6,
        external_high=None,
        external_low=None,
    )


def test_only_the_latest_break_is_used():
    events = [bos("bearish", 95, 3), bos("bullish", 110, 9)]
    result = find_external_structure(UP_SWINGS, events, MarketState.RANGING)
    assert result == ExternalStructure(
        direction=MarketState.UPTREND,
        protected_high=None,
        protected_low=L6,
        external_high=H4,
        external_low=None,
    )


def test_latest_swing_wins_when_prices_are_equal():
    swings = [swing(2, 110, HIGH), swing(3, 100, LOW), swing(6, 110, HIGH)]
    result = find_external_structure(
        swings, [bos("bullish", 110, 8)], MarketState.RANGING
    )
    assert result.external_high.index == 6
    assert result.protected_low.index == 3


def test_unknown_break_direction_gives_an_empty_structure():
    result = find_external_structure(
        UP_SWINGS, [bos("neutral", 110, 5)], MarketState.RANGING
    )
    assert result == ExternalStructure(
        direction=MarketState.RANGING,
        protected_high=None,
        protected_low=None,
        external_high=None,
        external_low=None,
    )


# ---- should_promote_to_external ----------------------------------------------


@pytest.mark.parametrize("price, expected", [(111, True), (110, False), (109, False)])
def test_uptrend_promotes_only_a_higher_high(price, expected):
    external = structure(MarketState.UPTREND, external_high=swing(4, 110, HIGH))
    assert should_promote_to_external(swing(9, price, HIGH), external) is expected


def test_uptrend_never_promotes_a_low():
    external = structure(MarketState.UPTREND, external_high=swing(4, 110, HIGH))
    assert should_promote_to_external(swing(9, 50, LOW), external) is False


def test_uptrend_without_an_external_high_never_promotes():
    external = structure(MarketState.UPTREND)
    assert should_promote_to_external(swing(9, 500, HIGH), external) is False


@pytest.mark.parametrize("price, expected", [(89, True), (90, False), (91, False)])
def test_downtrend_promotes_only_a_lower_low(price, expected):
    external = structure(MarketState.DOWNTREND, external_low=swing(4, 90, LOW))
    assert should_promote_to_external(swing(9, price, LOW), external) is expected


def test_downtrend_never_promotes_a_high():
    external = structure(MarketState.DOWNTREND, external_low=swing(4, 90, LOW))
    assert should_promote_to_external(swing(9, 500, HIGH), external) is False


def test_downtrend_without_an_external_low_never_promotes():
    external = structure(MarketState.DOWNTREND)
    assert should_promote_to_external(swing(9, 1, LOW), external) is False


@pytest.mark.parametrize("state", [MarketState.RANGING, MarketState.UNDEFINED])
def test_nothing_is_promoted_outside_a_trend(state):
    external = structure(
        state, external_high=swing(4, 110, HIGH), external_low=swing(5, 90, LOW)
    )
    assert should_promote_to_external(swing(9, 500, HIGH), external) is False
    assert should_promote_to_external(swing(9, 1, LOW), external) is False
