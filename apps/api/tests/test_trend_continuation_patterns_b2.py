from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.trend_continuation import (
    _is_bearish_inside_bar_breakout,
    _is_bullish_inside_bar_breakout,
    _is_falling_three_methods,
    _is_rising_three_methods,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
CASE = "rows, index, level, expected"


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


def replace(rows, position, row):
    updated = list(rows)
    updated[position] = row
    return updated


def case(rows, index, level, expected, id_):
    return pytest.param(rows, index, level, expected, id=id_)


# Level is 100 unless a case says otherwise. Rows are (open, close, high, low).

RISING = [
    (100, 110, 111, 99),
    (108, 106, 109, 105),
    (106, 104, 107, 103),
    (104, 102, 105, 101),
    (103, 113, 113.5, 102.5),
]
RISING_CASES = [
    case(RISING, 4, 100, True, "canonical"),
    case(replace(RISING, 4, (106.5, 111.5, 112, 106)), 4, 100, True, "fifth-body-exactly-half"),
    case(replace(RISING, 4, (106.6, 111.5, 112, 106)), 4, 100, False, "fifth-body-just-under-half"),
    case(replace(RISING, 4, (101, 111, 111.5, 100.5)), 4, 100, False, "fifth-close-equals-first-high"),
    case(RISING, 4, 115, False, "level-above-fifth-close"),
    case(replace(RISING, 0, (110, 100, 111, 99)), 4, 100, False, "first-is-bearish"),
    case(replace(RISING, 1, (106, 108, 109, 105)), 4, 100, False, "second-is-bullish"),
    case(replace(RISING, 2, (104, 106, 107, 103)), 4, 100, False, "third-is-bullish"),
    case(replace(RISING, 3, (102, 104, 105, 101)), 4, 100, False, "fourth-is-bullish"),
    case(replace(RISING, 4, (118, 112, 118.5, 111.5)), 4, 100, False, "fifth-is-bearish"),
    case(replace(RISING, 1, (108, 106, 111, 105)), 4, 100, False, "second-high-equals-first-high"),
    case(replace(RISING, 2, (106, 104, 107, 99)), 4, 100, False, "third-low-equals-first-low"),
    case(replace(RISING, 3, (104, 102, 111.5, 101)), 4, 100, False, "fourth-high-above-first-high"),
    case(replace(RISING, 1, (108, 106, 109, 98.5)), 4, 100, False, "second-low-below-first-low"),
    case(RISING, 3, 100, False, "index-too-early"),
    case(replace(RISING, 0, (105, 105, 111, 99)), 4, 100, False, "first-body-zero"),
]

FALLING = [
    (110, 100, 111, 99),
    (102, 104, 105, 101),
    (104, 106, 107, 103),
    (106, 108, 109, 105),
    (107, 97, 107.5, 96.5),
]
FALLING_CASES = [
    case(FALLING, 4, 100, True, "canonical"),
    case(replace(FALLING, 4, (103.5, 98.5, 104, 98)), 4, 100, True, "fifth-body-exactly-half"),
    case(replace(FALLING, 4, (103.4, 98.5, 104, 98)), 4, 100, False, "fifth-body-just-under-half"),
    case(replace(FALLING, 4, (109, 99, 109.5, 98.5)), 4, 100, False, "fifth-close-equals-first-low"),
    case(FALLING, 4, 95, False, "level-below-fifth-close"),
    case(replace(FALLING, 0, (100, 110, 111, 99)), 4, 100, False, "first-is-bullish"),
    case(replace(FALLING, 1, (104, 102, 105, 101)), 4, 100, False, "second-is-bearish"),
    case(replace(FALLING, 2, (106, 104, 107, 103)), 4, 100, False, "third-is-bearish"),
    case(replace(FALLING, 3, (108, 106, 109, 105)), 4, 100, False, "fourth-is-bearish"),
    case(replace(FALLING, 4, (92, 97.5, 98, 91.5)), 4, 100, False, "fifth-is-bullish"),
    case(replace(FALLING, 1, (102, 104, 111, 101)), 4, 100, False, "second-high-equals-first-high"),
    case(replace(FALLING, 2, (104, 106, 107, 99)), 4, 100, False, "third-low-equals-first-low"),
    case(replace(FALLING, 3, (106, 108, 109, 98.5)), 4, 100, False, "fourth-low-below-first-low"),
    case(replace(FALLING, 1, (102, 104, 111.5, 101)), 4, 100, False, "second-high-above-first-high"),
    case(FALLING, 3, 100, False, "index-too-early"),
    case(replace(FALLING, 0, (105, 105, 111, 99)), 4, 100, False, "first-body-zero"),
]

INSIDE_BULL = [(100, 103, 105, 99), (101, 102, 104, 100), (103, 106, 106.5, 102.5)]
INSIDE_BULL_CASES = [
    case(INSIDE_BULL, 2, 100, True, "canonical"),
    case(replace(INSIDE_BULL, 1, (101, 102, 105, 100)), 2, 100, True, "inside-high-equals-mother-high"),
    case(replace(INSIDE_BULL, 1, (101, 102, 104, 99)), 2, 100, True, "inside-low-equals-mother-low"),
    case(replace(INSIDE_BULL, 1, (101, 102, 105.5, 100)), 2, 100, False, "inside-high-above-mother-high"),
    case(replace(INSIDE_BULL, 1, (101, 102, 104, 98.5)), 2, 100, False, "inside-low-below-mother-low"),
    case(replace(INSIDE_BULL, 2, (106.5, 105.5, 107, 105)), 2, 100, False, "breakout-is-bearish"),
    case(replace(INSIDE_BULL, 2, (103, 105, 105.5, 102.5)), 2, 100, False, "close-equals-mother-high"),
    case(INSIDE_BULL, 2, 107, False, "level-above-breakout-close"),
    case(INSIDE_BULL, 1, 100, False, "index-too-early"),
]

INSIDE_BEAR = [(103, 100, 104, 98), (101, 100.5, 103, 99), (99, 96, 99.5, 95.5)]
INSIDE_BEAR_CASES = [
    case(INSIDE_BEAR, 2, 100, True, "canonical"),
    case(replace(INSIDE_BEAR, 1, (101, 100.5, 104, 99)), 2, 100, True, "inside-high-equals-mother-high"),
    case(replace(INSIDE_BEAR, 1, (101, 100.5, 103, 98)), 2, 100, True, "inside-low-equals-mother-low"),
    case(replace(INSIDE_BEAR, 1, (101, 100.5, 104.5, 99)), 2, 100, False, "inside-high-above-mother-high"),
    case(replace(INSIDE_BEAR, 1, (101, 100.5, 103, 97.5)), 2, 100, False, "inside-low-below-mother-low"),
    case(replace(INSIDE_BEAR, 2, (95, 96, 96.5, 94.5)), 2, 100, False, "breakout-is-bullish"),
    case(replace(INSIDE_BEAR, 2, (99, 98, 99.5, 97.5)), 2, 100, False, "close-equals-mother-low"),
    case(INSIDE_BEAR, 2, 95, False, "level-below-breakout-close"),
    case(INSIDE_BEAR, 1, 100, False, "index-too-early"),
]


@pytest.mark.parametrize(CASE, RISING_CASES)
def test_rising_three_methods(rows, index, level, expected):
    assert _is_rising_three_methods(candles_from(rows), index, level) is expected


@pytest.mark.parametrize(CASE, FALLING_CASES)
def test_falling_three_methods(rows, index, level, expected):
    assert _is_falling_three_methods(candles_from(rows), index, level) is expected


@pytest.mark.parametrize(CASE, INSIDE_BULL_CASES)
def test_bullish_inside_bar_breakout(rows, index, level, expected):
    result = _is_bullish_inside_bar_breakout(candles_from(rows), index, level)
    assert result is expected


@pytest.mark.parametrize(CASE, INSIDE_BEAR_CASES)
def test_bearish_inside_bar_breakout(rows, index, level, expected):
    result = _is_bearish_inside_bar_breakout(candles_from(rows), index, level)
    assert result is expected
