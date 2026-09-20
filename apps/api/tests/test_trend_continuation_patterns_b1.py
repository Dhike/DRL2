from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.trend_continuation import (
    _is_evening_star,
    _is_morning_star,
    _is_three_black_crows,
    _is_three_white_soldiers,
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

MORNING = [(108, 102, 108.5, 101.5), (101, 100.5, 101.5, 100), (101, 106, 106.5, 99.5)]
MORNING_CASES = [
    case(MORNING, 2, 100, True, "canonical"),
    case(replace(MORNING, 1, (101, 104, 104.5, 100.5)), 2, 100, True, "middle-body-exactly-half"),
    case(replace(MORNING, 1, (101, 104.2, 104.5, 100.5)), 2, 100, False, "middle-body-just-over-half"),
    case(replace(MORNING, 0, (102, 108, 108.5, 101.5)), 2, 100, False, "first-is-bullish"),
    case(replace(MORNING, 2, (107, 106, 107.5, 99.5)), 2, 100, False, "third-is-bearish"),
    case(replace(MORNING, 2, (101, 105, 105.5, 99.5)), 2, 100, False, "third-close-equals-midpoint"),
    case(MORNING, 2, 106, False, "level-equals-third-close"),
    case(replace(MORNING, 2, (101.2, 106, 106.5, 100.5)), 2, 100, False, "third-low-above-level"),
    case(replace(MORNING, 2, (101, 106, 106.5, 100.0)), 2, 100, True, "third-low-exactly-level"),
    case(MORNING, 1, 100, False, "index-too-early"),
    case(replace(MORNING, 0, (105, 105, 105.5, 104.5)), 2, 100, False, "first-body-zero"),
]

EVENING = [(92, 98, 98.5, 91.5), (99, 99.5, 100, 98.5), (99, 94, 100.5, 93.5)]
EVENING_CASES = [
    case(EVENING, 2, 100, True, "canonical"),
    case(replace(EVENING, 1, (99, 96, 99.5, 95.5)), 2, 100, True, "middle-body-exactly-half"),
    case(replace(EVENING, 1, (99, 95.8, 99.5, 95.5)), 2, 100, False, "middle-body-just-over-half"),
    case(replace(EVENING, 0, (98, 92, 98.5, 91.5)), 2, 100, False, "first-is-bearish"),
    case(replace(EVENING, 2, (93, 94, 100.5, 92.5)), 2, 100, False, "third-is-bullish"),
    case(replace(EVENING, 2, (99, 95, 100.5, 94.5)), 2, 100, False, "third-close-equals-midpoint"),
    case(EVENING, 2, 94, False, "level-equals-third-close"),
    case(replace(EVENING, 2, (99, 94, 99.9, 93.5)), 2, 100, False, "third-high-below-level"),
    case(replace(EVENING, 2, (99, 94, 100.0, 93.5)), 2, 100, True, "third-high-exactly-level"),
    case(EVENING, 1, 100, False, "index-too-early"),
    case(replace(EVENING, 0, (95, 95, 95.5, 94.5)), 2, 100, False, "first-body-zero"),
]

SOLDIERS = [(99, 101, 101.5, 98.5), (100, 103, 103.5, 99.5), (101, 105, 105.5, 100)]
SOLDIERS_CASES = [
    case(SOLDIERS, 2, 100, True, "canonical-third-low-exactly-level"),
    case(replace(SOLDIERS, 2, (101, 105, 105.5, 100.2)), 2, 100, False, "third-low-above-level"),
    case(replace(SOLDIERS, 0, (99.5, 99, 100, 98.5)), 2, 100, False, "first-is-bearish"),
    case(
        replace(replace(SOLDIERS, 1, (103.4, 103, 103.6, 102.8)), 2, (103.6, 105, 105.5, 100)),
        2, 100, False, "second-is-bearish",
    ),
    case(replace(SOLDIERS, 2, (105.2, 105, 105.5, 100)), 2, 100, False, "third-is-bearish"),
    case(replace(SOLDIERS, 1, (100, 101, 101.5, 99.5)), 2, 100, False, "second-close-equals-first-close"),
    case(replace(SOLDIERS, 2, (101, 103, 103.5, 100)), 2, 100, False, "third-close-equals-second-close"),
    case(replace(SOLDIERS, 1, (99, 103, 103.5, 98.5)), 2, 100, False, "second-open-equals-first-open"),
    case(replace(SOLDIERS, 2, (100, 105, 105.5, 100)), 2, 100, False, "third-open-equals-second-open"),
    case(SOLDIERS, 2, 105, False, "level-equals-third-close"),
    case(SOLDIERS, 1, 100, False, "index-too-early"),
]

CROWS = [(101, 99, 101.5, 98.5), (100, 97, 100.5, 96.5), (99, 95, 100, 94.5)]
CROWS_CASES = [
    case(CROWS, 2, 100, True, "canonical-third-high-exactly-level"),
    case(replace(CROWS, 2, (99, 95, 99.8, 94.5)), 2, 100, False, "third-high-below-level"),
    case(replace(CROWS, 0, (100.5, 101, 101.5, 100)), 2, 100, False, "first-is-bullish"),
    case(
        replace(replace(CROWS, 1, (96.6, 97, 97.2, 96.4)), 2, (96.4, 95, 100, 94.5)),
        2, 100, False, "second-is-bullish",
    ),
    case(replace(CROWS, 2, (96, 96.5, 100, 95.5)), 2, 100, False, "third-is-bullish"),
    case(replace(CROWS, 1, (100, 99, 100.5, 98.5)), 2, 100, False, "second-close-equals-first-close"),
    case(replace(CROWS, 2, (99, 97, 100, 96.5)), 2, 100, False, "third-close-equals-second-close"),
    case(replace(CROWS, 1, (101, 97, 101.5, 96.5)), 2, 100, False, "second-open-equals-first-open"),
    case(replace(CROWS, 2, (100, 95, 100.5, 94.5)), 2, 100, False, "third-open-equals-second-open"),
    case(CROWS, 2, 95, False, "level-equals-third-close"),
    case(CROWS, 1, 100, False, "index-too-early"),
]


@pytest.mark.parametrize(CASE, MORNING_CASES)
def test_morning_star(rows, index, level, expected):
    assert _is_morning_star(candles_from(rows), index, level) is expected


@pytest.mark.parametrize(CASE, EVENING_CASES)
def test_evening_star(rows, index, level, expected):
    assert _is_evening_star(candles_from(rows), index, level) is expected


@pytest.mark.parametrize(CASE, SOLDIERS_CASES)
def test_three_white_soldiers(rows, index, level, expected):
    assert _is_three_white_soldiers(candles_from(rows), index, level) is expected


@pytest.mark.parametrize(CASE, CROWS_CASES)
def test_three_black_crows(rows, index, level, expected):
    assert _is_three_black_crows(candles_from(rows), index, level) is expected
