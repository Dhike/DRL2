from datetime import datetime, timezone

import pytest

from app.market.models import Candle
from app.scanner.level_loss import LevelLossPolicy, has_level_been_lost

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
STRICT, TOLERANT = LevelLossPolicy.STRICT, LevelLossPolicy.TOLERANT


def candle(close, open_=None, high=None, low=None):
    open_ = close if open_ is None else open_
    high = max(open_, close) + 1.0 if high is None else high
    low = min(open_, close) - 1.0 if low is None else low
    return Candle(
        timestamp=BASE, open=open_, high=high, low=low, close=close, volume=1.0
    )


@pytest.mark.parametrize(
    "close, expected",
    [
        pytest.param(101.0, False, id="well-above-level"),
        pytest.param(100.0, False, id="closes-exactly-on-the-level"),
        pytest.param(99.99, True, id="closes-a-hair-below"),
        pytest.param(90.0, True, id="closes-well-below"),
    ],
)
def test_strict_bullish(close, expected):
    assert has_level_been_lost(candle(close), 100.0, "bullish", STRICT) is expected


@pytest.mark.parametrize(
    "close, expected",
    [
        pytest.param(99.0, False, id="well-below-level"),
        pytest.param(100.0, False, id="closes-exactly-on-the-level"),
        pytest.param(100.01, True, id="closes-a-hair-above"),
        pytest.param(110.0, True, id="closes-well-above"),
    ],
)
def test_strict_bearish(close, expected):
    assert has_level_been_lost(candle(close), 100.0, "bearish", STRICT) is expected


def test_strict_ignores_the_wick_and_only_checks_the_close():
    # Low wicks well below the level, but the close holds above it.
    wicked_candle = candle(close=100.5, open_=101.0, high=101.5, low=90.0)
    assert has_level_been_lost(wicked_candle, 100.0, "bullish", STRICT) is False


@pytest.mark.parametrize(
    "close, tolerance, expected",
    [
        pytest.param(99.0, 2.0, False, id="within-tolerance"),
        pytest.param(98.0, 2.0, False, id="exactly-at-the-tolerance-edge"),
        pytest.param(97.99, 2.0, True, id="just-beyond-tolerance"),
        pytest.param(90.0, 2.0, True, id="well-beyond-tolerance"),
        pytest.param(99.0, 0.0, True, id="zero-tolerance-behaves-like-strict"),
    ],
)
def test_tolerant_bullish(close, tolerance, expected):
    result = has_level_been_lost(
        candle(close), 100.0, "bullish", TOLERANT, tolerance=tolerance
    )
    assert result is expected


@pytest.mark.parametrize(
    "close, tolerance, expected",
    [
        pytest.param(101.0, 2.0, False, id="within-tolerance"),
        pytest.param(102.0, 2.0, False, id="exactly-at-the-tolerance-edge"),
        pytest.param(102.01, 2.0, True, id="just-beyond-tolerance"),
    ],
)
def test_tolerant_bearish(close, tolerance, expected):
    result = has_level_been_lost(
        candle(close), 100.0, "bearish", TOLERANT, tolerance=tolerance
    )
    assert result is expected


def test_tolerance_is_ignored_under_strict_policy():
    # Even with a generous tolerance passed in, STRICT should ignore it.
    result = has_level_been_lost(
        candle(99.0), 100.0, "bullish", STRICT, tolerance=5.0
    )
    assert result is True


def test_unknown_direction_raises():
    with pytest.raises(ValueError, match="Unknown direction"):
        has_level_been_lost(candle(99.0), 100.0, "sideways", STRICT)
