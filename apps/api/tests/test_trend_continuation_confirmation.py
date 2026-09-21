from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.structure import BreakOfStructure
from app.scanner.trend_continuation import (
    TrendContinuationRetest,
    detect_confirmation,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candles_from(rows):
    """Each row is (open, close, high, low)."""
    return [
        Candle(
            timestamp=T0 + timedelta(hours=i),
            open=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=1.0,
        )
        for i, (open_, close, high, low) in enumerate(rows)
    ]


def run(rows, retest_index, direction="bullish", level=100.0):
    candles = candles_from(rows)
    bos = BreakOfStructure(
        direction=direction,
        broken_level=level,
        candle_index=0,
        candle_timestamp=T0,
    )
    retest = TrendContinuationRetest(
        direction=direction,
        break_level=level,
        break_index=0,
        retest_index=retest_index,
        candle=candles[min(retest_index, len(candles) - 1)],
        bos=bos,
    )
    return retest, candles, detect_confirmation(candles, retest)


# Rows are (open, close, high, low); the level is 100 unless a test says otherwise.
RETEST_BULL = (101, 100.5, 101.5, 100)
RETEST_BEAR = (99, 99.5, 100, 98.5)

HAMMER = (101.5, 102.0, 102.25, 98.0)
PIN_BULL = (101, 102, 103.5, 98)
MARU_BULL = (99.5, 105.0, 105.25, 99.25)
OUTSIDE_PREV = (100, 101, 102, 99)
OUTSIDE_BULL = (99.5, 103.0, 103.5, 98.5)
PREV_BEAR = (102, 100.5, 102.5, 100)
ENGULF_BULL = (100.0, 103.0, 104.5, 100.0)
MORNING_ROWS = [
    (108, 102, 108.5, 101.5),
    (101.5, 101.0, 102.0, 100.0),
    (102.0, 106.0, 106.5, 100.0),
]
SOLDIER_ROWS = [
    (99, 100, 101, 98),
    (99, 101, 101.5, 98.5),
    (100, 103, 103.5, 99.5),
    (101, 105, 105.5, 100.0),
]
RISING_ROWS = [
    (100, 110, 111, 99),
    (108, 106, 109, 105),
    (106, 104, 107, 103),
    (104, 102, 105, 101),
    (103, 113, 113.5, 102.5),
]
INSIDE_BULL_ROWS = [(100, 103, 105, 99), (101, 102, 104, 100), (103, 106, 106.5, 102.5)]

STAR = (98.5, 98.0, 102.0, 97.75)
PIN_BEAR = (99, 98, 102, 96.5)
MARU_BEAR = (100.5, 95.0, 100.75, 94.75)
OUTSIDE_BEAR = (102.5, 98.0, 103.0, 97.5)
PREV_BULL = (98, 99.5, 100, 97.5)
ENGULF_BEAR = (100.0, 97.0, 100.0, 95.5)
EVENING_ROWS = [
    (92, 98, 98.5, 91.5),
    (98.5, 99.0, 100.0, 98.0),
    (98.0, 94.0, 100.0, 93.5),
]
CROWS_ROWS = [
    (101, 100, 102, 99),
    (101, 99, 101.5, 98.5),
    (100, 97, 100.5, 96.5),
    (99, 95, 100.0, 94.5),
]
FALLING_ROWS = [
    (110, 100, 111, 99),
    (102, 104, 105, 101),
    (104, 106, 107, 103),
    (106, 108, 109, 105),
    (107, 97, 108.5, 95.5),
]
INSIDE_BEAR_ROWS = [(103, 100, 104, 98), (101, 100.5, 103, 99), (99, 96, 99.5, 95.5)]

PATTERN_CASES = [
    pytest.param("bullish", [RETEST_BULL, HAMMER], 0, "hammer", 1, id="hammer"),
    pytest.param("bullish", [RETEST_BULL, PIN_BULL], 0, "bullish_pin_bar", 1, id="bullish-pin-bar"),
    pytest.param("bullish", [RETEST_BULL, MARU_BULL], 0, "bullish_marubozu", 1, id="bullish-marubozu"),
    pytest.param("bullish", [OUTSIDE_PREV, OUTSIDE_BULL], 0, "bullish_outside_bar", 1, id="bullish-outside-bar"),
    pytest.param("bullish", [PREV_BEAR, ENGULF_BULL], 0, "bullish_engulfing", 1, id="bullish-engulfing"),
    pytest.param("bullish", MORNING_ROWS, 0, "morning_star", 2, id="morning-star"),
    pytest.param("bullish", SOLDIER_ROWS, 0, "three_white_soldiers", 3, id="three-white-soldiers"),
    pytest.param("bullish", RISING_ROWS, 0, "rising_three_methods", 4, id="rising-three-methods"),
    pytest.param("bullish", INSIDE_BULL_ROWS, 0, "bullish_inside_bar_breakout", 2, id="bullish-inside-bar-breakout"),
    pytest.param("bearish", [RETEST_BEAR, STAR], 0, "shooting_star", 1, id="shooting-star"),
    pytest.param("bearish", [RETEST_BEAR, PIN_BEAR], 0, "bearish_pin_bar", 1, id="bearish-pin-bar"),
    pytest.param("bearish", [RETEST_BEAR, MARU_BEAR], 0, "bearish_marubozu", 1, id="bearish-marubozu"),
    pytest.param("bearish", [OUTSIDE_PREV, OUTSIDE_BEAR], 0, "bearish_outside_bar", 1, id="bearish-outside-bar"),
    pytest.param("bearish", [PREV_BULL, ENGULF_BEAR], 0, "bearish_engulfing", 1, id="bearish-engulfing"),
    pytest.param("bearish", EVENING_ROWS, 0, "evening_star", 2, id="evening-star"),
    pytest.param("bearish", CROWS_ROWS, 0, "three_black_crows", 3, id="three-black-crows"),
    pytest.param("bearish", FALLING_ROWS, 0, "falling_three_methods", 4, id="falling-three-methods"),
    pytest.param("bearish", INSIDE_BEAR_ROWS, 0, "bearish_inside_bar_breakout", 2, id="bearish-inside-bar-breakout"),
]

PRIORITY_CASES = [
    pytest.param("bullish", [RETEST_BULL, HAMMER], "hammer", id="hammer-beats-pin-bar"),
    pytest.param("bullish", [OUTSIDE_PREV, (98.6, 105.0, 105.1, 98.5)], "bullish_marubozu", id="marubozu-beats-outside-bar"),
    pytest.param("bullish", [PREV_BEAR, (100.0, 103.0, 103.5, 99.0)], "bullish_outside_bar", id="outside-bar-beats-engulfing"),
    pytest.param("bearish", [OUTSIDE_PREV, (102.6, 96.0, 102.7, 95.9)], "bearish_marubozu", id="bearish-marubozu-beats-outside-bar"),
    pytest.param("bearish", [PREV_BULL, (100.0, 97.0, 101.0, 96.5)], "bearish_outside_bar", id="bearish-outside-bar-beats-engulfing"),
]


@pytest.mark.parametrize("direction, rows, retest_index, pattern, index", PATTERN_CASES)
def test_each_pattern_is_recognised(direction, rows, retest_index, pattern, index):
    _, candles, result = run(rows, retest_index, direction)
    assert result is not None
    assert (result.pattern, result.confirmation_index, result.direction) == (
        pattern,
        index,
        direction,
    )
    assert result.candle == candles[index]


@pytest.mark.parametrize("direction, rows, pattern", PRIORITY_CASES)
def test_pattern_priority(direction, rows, pattern):
    _, _, result = run(rows, 0, direction)
    assert result is not None
    assert (result.pattern, result.confirmation_index) == (pattern, 1)


def test_pattern_on_the_retest_candle_is_ignored():
    _, _, result = run([HAMMER], 0)
    assert result is None


def test_first_matching_candle_wins():
    _, _, result = run([RETEST_BULL, HAMMER, MARU_BULL], 0)
    assert (result.pattern, result.confirmation_index) == ("hammer", 1)


def test_scanning_continues_past_candles_without_a_pattern():
    filler = (101, 101.5, 102, 100.8)
    retest_candle = (100, 100.5, 101, 99.5)
    _, _, result = run([retest_candle, filler, HAMMER], 0)
    assert (result.pattern, result.confirmation_index) == ("hammer", 2)


@pytest.mark.parametrize(
    "direction, rows",
    [
        ("bearish", [RETEST_BEAR, HAMMER]),
        ("bullish", [RETEST_BULL, STAR]),
    ],
)
def test_patterns_of_the_other_direction_are_ignored(direction, rows):
    _, _, result = run(rows, 0, direction)
    assert result is None


def test_unknown_direction_finds_nothing():
    _, _, result = run([RETEST_BULL, HAMMER], 0, direction="neutral")
    assert result is None


@pytest.mark.parametrize("retest_index", [0, 5])
def test_no_candles_after_the_retest(retest_index):
    _, _, result = run([HAMMER], retest_index)
    assert result is None


def test_confirmation_carries_the_retest_and_candle():
    retest, candles, result = run([RETEST_BULL, HAMMER], 0)
    assert result.direction == "bullish"
    assert result.confirmation_index == 1
    assert result.pattern == "hammer"
    assert result.candle == candles[1]
    assert result.retest is retest


def test_level_comes_from_the_retest():
    _, _, result = run([RETEST_BULL, HAMMER], 0, level=103.0)
    assert result is None


def test_last_candle_of_a_pattern_must_come_after_the_retest():
    _, _, result = run(MORNING_ROWS, 2)
    assert result is None
