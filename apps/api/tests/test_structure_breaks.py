from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.structure import (
    ChangeOfCharacter,
    ExternalStructure,
    MarketState,
    StructureLabel,
    SwingPoint,
    SwingType,
    detect_bos,
    detect_choch,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
HIGH, LOW = SwingType.HIGH, SwingType.LOW


def candles_from_closes(closes):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=float(close),
            high=close + 0.5,
            low=close - 0.5,
            close=float(close),
            volume=1.0,
        )
        for i, close in enumerate(closes)
    ]


def swing(index, price, kind, labeled=True):
    label = None
    if labeled:
        label = StructureLabel.HH if kind is HIGH else StructureLabel.HL
    return SwingPoint(
        index=index,
        timestamp=BASE + timedelta(hours=index),
        price=float(price),
        swing_type=kind,
        label=label,
    )


def breaks(closes, swings):
    events = detect_bos(candles_from_closes(closes), swings)
    return [(e.direction, e.broken_level, e.candle_index) for e in events]


def external(direction, protected_high=None, protected_low=None):
    return ExternalStructure(
        direction=direction,
        protected_high=protected_high,
        protected_low=protected_low,
        external_high=None,
        external_low=None,
    )


# ---- detect_bos --------------------------------------------------------------


@pytest.mark.parametrize(
    "swings",
    [[], [swing(1, 110, HIGH, labeled=False)]],
)
def test_no_labeled_swings_no_events(swings):
    assert breaks([100, 105, 120], swings) == []


def test_bullish_break_on_close_above_swing_high():
    candles = candles_from_closes([100, 105, 108, 109, 111, 112])
    events = detect_bos(candles, [swing(1, 110, HIGH)])
    assert [(e.direction, e.broken_level, e.candle_index) for e in events] == [
        ("bullish", 110.0, 4)
    ]
    assert events[0].candle_timestamp == candles[4].timestamp


def test_bearish_break_on_close_below_swing_low():
    result = breaks([100, 95, 92, 91, 89, 88], [swing(1, 90, LOW)])
    assert result == [("bearish", 90.0, 4)]


@pytest.mark.parametrize(
    "closes, swings",
    [
        ([100, 105, 108, 110, 110], [swing(1, 110, HIGH)]),
        ([100, 95, 92, 90, 90], [swing(1, 90, LOW)]),
    ],
)
def test_equal_close_is_not_a_break(closes, swings):
    assert breaks(closes, swings) == []


def test_swing_cannot_be_broken_on_its_own_candle():
    result = breaks([100, 101, 102, 115, 116], [swing(3, 110, HIGH)])
    assert result == [("bullish", 110.0, 4)]


def test_latest_swing_is_used_not_the_highest():
    swings = [swing(1, 120, HIGH), swing(3, 110, HIGH)]
    result = breaks([100, 101, 102, 103, 115, 121], swings)
    assert result == [("bullish", 110.0, 4)]


def test_bullish_then_bearish_alternation():
    swings = [swing(1, 110, HIGH), swing(5, 100, LOW)]
    result = breaks([100, 105, 108, 111, 112, 104, 99, 98], swings)
    assert result == [("bullish", 110.0, 3), ("bearish", 100.0, 6)]


def test_bearish_then_bullish_alternation():
    swings = [swing(1, 90, LOW), swing(5, 100, HIGH)]
    result = breaks([100, 95, 92, 89, 88, 96, 101, 102], swings)
    assert result == [("bearish", 90.0, 3), ("bullish", 100.0, 6)]


def test_no_second_break_while_waiting_for_new_structure():
    swings = [swing(1, 110, HIGH), swing(4, 118, HIGH)]
    result = breaks([100, 105, 108, 111, 116, 119, 125], swings)
    assert result == [("bullish", 110.0, 3)]


def test_swing_before_the_break_does_not_clear_waiting():
    swings = [swing(1, 110, HIGH), swing(2, 100, LOW)]
    result = breaks([100, 105, 106, 111, 99, 98], swings)
    assert result == [("bullish", 110.0, 3)]


def test_no_candles_no_events():
    assert detect_bos([], [swing(1, 110, HIGH)]) == []


# ---- detect_choch ------------------------------------------------------------


def test_uptrend_choch_is_bearish_on_close_below_protected_low():
    candles = candles_from_closes([105, 103, 101, 99, 98])
    result = detect_choch(
        candles, external(MarketState.UPTREND, protected_low=swing(2, 100, LOW))
    )
    assert result == ChangeOfCharacter(
        direction="bearish",
        broken_level=100.0,
        candle_index=3,
        candle_timestamp=candles[3].timestamp,
        previous_direction=MarketState.UPTREND,
    )


def test_downtrend_choch_is_bullish_on_close_above_protected_high():
    candles = candles_from_closes([105, 108, 111, 112])
    result = detect_choch(
        candles, external(MarketState.DOWNTREND, protected_high=swing(2, 110, HIGH))
    )
    assert result == ChangeOfCharacter(
        direction="bullish",
        broken_level=110.0,
        candle_index=2,
        candle_timestamp=candles[2].timestamp,
        previous_direction=MarketState.DOWNTREND,
    )


def test_choch_needs_a_close_not_a_wick():
    candles = candles_from_closes([105, 104, 102, 104])
    candles[2] = Candle(
        timestamp=candles[2].timestamp,
        open=104.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=1.0,
    )
    result = detect_choch(
        candles, external(MarketState.UPTREND, protected_low=swing(1, 100, LOW))
    )
    assert result is None


@pytest.mark.parametrize(
    "ext, closes",
    [
        (external(MarketState.UPTREND, protected_low=swing(1, 100, LOW)), [105, 100]),
        (
            external(MarketState.DOWNTREND, protected_high=swing(1, 110, HIGH)),
            [105, 110],
        ),
    ],
)
def test_choch_equal_close_is_not_a_break(ext, closes):
    assert detect_choch(candles_from_closes(closes), ext) is None


def test_choch_returns_the_first_break():
    result = detect_choch(
        candles_from_closes([99, 98, 97]),
        external(MarketState.UPTREND, protected_low=swing(1, 100, LOW)),
    )
    assert result is not None
    assert (result.candle_index, result.broken_level) == (0, 100.0)


@pytest.mark.parametrize(
    "ext, closes",
    [
        (external(MarketState.UPTREND), [50]),
        (external(MarketState.DOWNTREND), [500]),
    ],
)
def test_choch_needs_the_protected_level(ext, closes):
    assert detect_choch(candles_from_closes(closes), ext) is None


@pytest.mark.parametrize("state", [MarketState.RANGING, MarketState.UNDEFINED])
def test_choch_only_in_trending_states(state):
    ext = external(
        state, protected_high=swing(3, 110, HIGH), protected_low=swing(2, 100, LOW)
    )
    assert detect_choch(candles_from_closes([200, 50]), ext) is None


def test_choch_no_candles():
    ext = external(MarketState.UPTREND, protected_low=swing(2, 100, LOW))
    assert detect_choch([], ext) is None


def test_uptrend_choch_ignores_closes_above_the_protected_high():
    ext = external(
        MarketState.UPTREND,
        protected_high=swing(3, 110, HIGH),
        protected_low=swing(2, 100, LOW),
    )
    assert detect_choch(candles_from_closes([105, 112, 115]), ext) is None
