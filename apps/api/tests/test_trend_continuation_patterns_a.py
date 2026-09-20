from datetime import datetime, timezone

import pytest

from app.market.models import Candle
from app.scanner.trend_continuation import (
    _is_bearish_engulfing,
    _is_bearish_marubozu,
    _is_bearish_outside_bar,
    _is_bearish_pin_bar,
    _is_bullish_engulfing,
    _is_bullish_marubozu,
    _is_bullish_outside_bar,
    _is_bullish_pin_bar,
    _is_hammer,
    _is_shooting_star,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candle(open_, close, high, low):
    return Candle(
        timestamp=T0,
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=1.0,
    )


def case(open_, close, high, low, level, expected, id_):
    return pytest.param(open_, close, high, low, level, expected, id=id_)


def pair(previous, current, level, expected, id_):
    return pytest.param(previous, current, level, expected, id=id_)


SINGLE = "open_, close, high, low, level, expected"
DOUBLE = "previous, current, level, expected"

# Candles are (open, close, high, low). All levels are 100 unless stated.

BULLISH_PIN_CASES = [
    case(101, 102, 102.5, 98, 100, True, "canonical"),
    case(101, 102, 102.5, 99, 100, True, "lower-wick-exactly-twice-the-body"),
    case(103, 104, 104.5, 101, 100, False, "low-above-level"),
    case(99, 100, 100.5, 97, 100, False, "close-equals-level"),
    case(102, 101, 102.5, 98, 100, False, "bearish-candle"),
    case(101, 102, 102.5, 99.5, 100, False, "lower-wick-too-short"),
    case(101, 102, 104, 99, 100, False, "upper-wick-equals-lower-wick"),
    case(101, 101, 101.5, 98, 100, False, "doji"),
    case(101, 101, 101, 101, 100, False, "zero-range"),
]

BEARISH_PIN_CASES = [
    case(99, 98, 102, 97.5, 100, True, "canonical"),
    case(99, 98, 101, 97.5, 100, True, "upper-wick-exactly-twice-the-body"),
    case(97, 96, 99, 95.5, 100, False, "high-below-level"),
    case(101, 100, 103, 99.5, 100, False, "close-equals-level"),
    case(98, 99, 102, 97.5, 100, False, "bullish-candle"),
    case(99, 98, 100.5, 97.5, 100, False, "upper-wick-too-short"),
    case(99, 98, 101, 96, 100, False, "lower-wick-equals-upper-wick"),
    case(99, 99, 102, 97.5, 100, False, "doji"),
    case(99, 99, 99, 99, 100, False, "zero-range"),
]

PREV_BEAR = (102, 100.5, 102.5, 100)
PREV_BULL = (98, 99.5, 100, 97.5)

BULLISH_ENGULFING_CASES = [
    pair(PREV_BEAR, (100.0, 103.0, 103.5, 99.0), 100, True, "canonical"),
    pair(PREV_BEAR, (100.5, 103.0, 103.5, 99.0), 100, True, "open-equals-previous-close"),
    pair(PREV_BEAR, (100.0, 102.0, 102.5, 99.0), 100, True, "close-equals-previous-open"),
    pair(PREV_BEAR, (100.5, 102.0, 102.5, 99.0), 100, False, "body-equal-to-previous-body"),
    pair(PREV_BEAR, (100.4, 103.0, 103.5, 100.2), 100, False, "low-above-level"),
    pair(PREV_BEAR, (100.0, 103.0, 103.5, 99.0), 104, False, "close-not-above-level"),
    pair(PREV_BEAR, (101.0, 103.0, 103.5, 99.0), 100, False, "open-above-previous-close"),
    pair(PREV_BEAR, (100.0, 101.9, 102.0, 99.0), 100, False, "close-below-previous-open"),
    pair(PREV_BEAR, (103.0, 99.5, 103.5, 99.0), 100, False, "bearish-candle"),
    pair((100.5, 102.0, 102.5, 100.0), (100.0, 103.0, 103.5, 99.0), 100, False, "previous-is-bullish"),
]

BEARISH_ENGULFING_CASES = [
    pair(PREV_BULL, (100.0, 97.0, 101.0, 96.5), 100, True, "canonical"),
    pair(PREV_BULL, (99.5, 97.0, 100.5, 96.5), 100, True, "open-equals-previous-close"),
    pair(PREV_BULL, (100.0, 98.0, 100.5, 97.5), 100, True, "close-equals-previous-open"),
    pair(PREV_BULL, (99.5, 98.0, 100.0, 97.5), 100, False, "body-equal-to-previous-body"),
    pair(PREV_BULL, (99.6, 97.0, 99.9, 96.5), 100, False, "high-below-level"),
    pair(PREV_BULL, (100.0, 97.0, 101.0, 96.5), 96, False, "close-not-below-level"),
    pair(PREV_BULL, (99.0, 97.0, 100.5, 96.5), 100, False, "open-below-previous-close"),
    pair(PREV_BULL, (100.0, 98.1, 100.5, 98.0), 100, False, "close-above-previous-open"),
    pair(PREV_BULL, (97.0, 100.5, 101.0, 96.5), 100, False, "bullish-candle"),
    pair((99.5, 98.0, 100.0, 97.5), (100.0, 97.0, 101.0, 96.5), 100, False, "previous-is-bearish"),
]

OUTSIDE_PREV = (100, 101, 102, 99)

BULLISH_OUTSIDE_CASES = [
    pair(OUTSIDE_PREV, (99.5, 103.0, 103.5, 98.5), 100, True, "canonical"),
    pair(OUTSIDE_PREV, (99.5, 101.5, 102.0, 98.5), 100, False, "high-equals-previous-high"),
    pair(OUTSIDE_PREV, (99.5, 103.0, 103.5, 99.0), 100, False, "low-equals-previous-low"),
    pair(OUTSIDE_PREV, (103.0, 99.5, 103.5, 98.5), 100, False, "bearish-candle"),
    pair(OUTSIDE_PREV, (99.5, 103.0, 103.5, 98.5), 104, False, "close-not-above-level"),
    pair(OUTSIDE_PREV, (99.5, 103.0, 103.5, 98.5), 90, True, "level-does-not-need-to-be-touched"),
]

BEARISH_OUTSIDE_CASES = [
    pair(OUTSIDE_PREV, (102.5, 98.0, 103.0, 97.5), 100, True, "canonical"),
    pair(OUTSIDE_PREV, (102.0, 98.0, 102.0, 97.5), 100, False, "high-equals-previous-high"),
    pair(OUTSIDE_PREV, (102.5, 99.5, 103.0, 99.0), 100, False, "low-equals-previous-low"),
    pair(OUTSIDE_PREV, (98.0, 102.0, 103.0, 97.5), 100, False, "bullish-candle"),
    pair(OUTSIDE_PREV, (102.5, 98.0, 103.0, 97.5), 96, False, "close-not-below-level"),
    pair(OUTSIDE_PREV, (102.5, 98.0, 103.0, 97.5), 110, True, "level-does-not-need-to-be-touched"),
]

BULLISH_MARUBOZU_CASES = [
    case(99.5, 105.0, 105.25, 99.25, 100, True, "canonical"),
    case(100, 117, 118.5, 98.5, 100, True, "body-exactly-85-percent-of-range"),
    case(100, 116.5, 118.5, 98.5, 100, False, "body-just-under-85-percent"),
    case(101, 106, 106.2, 100.8, 100, False, "low-above-level"),
    case(95, 100, 100.2, 94.8, 100, False, "close-equals-level"),
    case(105.0, 99.5, 105.25, 99.25, 100, False, "bearish-candle"),
    case(100, 100, 100, 100, 100, False, "zero-range"),
]

BEARISH_MARUBOZU_CASES = [
    case(100.5, 95.0, 100.75, 94.75, 100, True, "canonical"),
    case(100, 83, 101.5, 81.5, 100, True, "body-exactly-85-percent-of-range"),
    case(100, 83.5, 101.5, 81.5, 100, False, "body-just-under-85-percent"),
    case(99, 94, 99.2, 93.8, 100, False, "high-below-level"),
    case(105, 100, 105.2, 99.8, 100, False, "close-equals-level"),
    case(94.0, 99.5, 100.5, 93.8, 100, False, "bullish-candle"),
    case(100, 100, 100, 100, 100, False, "zero-range"),
]

HAMMER_CASES = [
    case(101.5, 102.0, 102.25, 98.0, 100, True, "canonical"),
    case(101, 102, 102.5, 99, 100, True, "lower-wick-exactly-twice-the-body"),
    case(101, 102, 103, 98, 100, True, "upper-wick-exactly-equal-to-the-body"),
    case(103, 104, 104.25, 101, 100, False, "low-above-level"),
    case(99, 100, 100.25, 97, 100, False, "close-equals-level"),
    case(102, 101.5, 102.25, 98, 100, False, "bearish-candle"),
    case(101, 102, 102.25, 99.5, 100, False, "lower-wick-too-short"),
    case(101, 102, 103.5, 98, 100, False, "upper-wick-longer-than-the-body"),
    case(101, 101, 101.5, 98, 100, False, "doji"),
    case(101, 101, 101, 101, 100, False, "zero-range"),
]

SHOOTING_STAR_CASES = [
    case(98.5, 98.0, 102.0, 97.75, 100, True, "canonical"),
    case(99, 98, 101, 97.5, 100, True, "upper-wick-exactly-twice-the-body"),
    case(99, 98, 102, 97, 100, True, "lower-wick-exactly-equal-to-the-body"),
    case(97, 96, 99, 95.5, 100, False, "high-below-level"),
    case(101, 100, 103, 99.5, 100, False, "close-equals-level"),
    case(98, 98.5, 102, 97.75, 100, False, "bullish-candle"),
    case(99, 98, 100.5, 97.5, 100, False, "upper-wick-too-short"),
    case(99, 98, 102, 96.5, 100, False, "lower-wick-longer-than-the-body"),
    case(98, 98, 102, 97.5, 100, False, "doji"),
    case(98, 98, 98, 98, 100, False, "zero-range"),
]


@pytest.mark.parametrize(SINGLE, BULLISH_PIN_CASES)
def test_bullish_pin_bar(open_, close, high, low, level, expected):
    assert _is_bullish_pin_bar(candle(open_, close, high, low), level) is expected


@pytest.mark.parametrize(SINGLE, BEARISH_PIN_CASES)
def test_bearish_pin_bar(open_, close, high, low, level, expected):
    assert _is_bearish_pin_bar(candle(open_, close, high, low), level) is expected


@pytest.mark.parametrize(DOUBLE, BULLISH_ENGULFING_CASES)
def test_bullish_engulfing(previous, current, level, expected):
    result = _is_bullish_engulfing(candle(*previous), candle(*current), level)
    assert result is expected


@pytest.mark.parametrize(DOUBLE, BEARISH_ENGULFING_CASES)
def test_bearish_engulfing(previous, current, level, expected):
    result = _is_bearish_engulfing(candle(*previous), candle(*current), level)
    assert result is expected


@pytest.mark.parametrize(DOUBLE, BULLISH_OUTSIDE_CASES)
def test_bullish_outside_bar(previous, current, level, expected):
    result = _is_bullish_outside_bar(candle(*previous), candle(*current), level)
    assert result is expected


@pytest.mark.parametrize(DOUBLE, BEARISH_OUTSIDE_CASES)
def test_bearish_outside_bar(previous, current, level, expected):
    result = _is_bearish_outside_bar(candle(*previous), candle(*current), level)
    assert result is expected


@pytest.mark.parametrize(SINGLE, BULLISH_MARUBOZU_CASES)
def test_bullish_marubozu(open_, close, high, low, level, expected):
    assert _is_bullish_marubozu(candle(open_, close, high, low), level) is expected


@pytest.mark.parametrize(SINGLE, BEARISH_MARUBOZU_CASES)
def test_bearish_marubozu(open_, close, high, low, level, expected):
    assert _is_bearish_marubozu(candle(open_, close, high, low), level) is expected


@pytest.mark.parametrize(SINGLE, HAMMER_CASES)
def test_hammer(open_, close, high, low, level, expected):
    assert _is_hammer(candle(open_, close, high, low), level) is expected


@pytest.mark.parametrize(SINGLE, SHOOTING_STAR_CASES)
def test_shooting_star(open_, close, high, low, level, expected):
    assert _is_shooting_star(candle(open_, close, high, low), level) is expected
