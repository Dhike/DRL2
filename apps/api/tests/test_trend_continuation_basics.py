from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.market.models import Candle
from app.scanner.structure import BreakOfStructure, StructureScope
from app.scanner.trend_continuation import (
    TrendContinuationBreak,
    TrendContinuationConfirmation,
    TrendContinuationRetest,
    TrendContinuationSignal,
    _body_size,
    _is_bearish,
    _is_bullish,
    _is_strong_bearish_candle,
    _is_strong_bullish_candle,
    _lower_wick,
    _range_size,
    _upper_wick,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
AVERAGE_BODY = 2.0  # strong candles need a body of at least 3.0


def candle(open_, close, high, low):
    return Candle(
        timestamp=T0,
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=1.0,
    )


def test_measurements_of_a_bullish_candle():
    c = candle(100, 103, 105, 98)
    assert (_body_size(c), _range_size(c), _upper_wick(c), _lower_wick(c)) == (
        3.0,
        7.0,
        2.0,
        2.0,
    )
    assert _is_bullish(c) is True
    assert _is_bearish(c) is False


def test_measurements_of_a_bearish_candle():
    c = candle(103, 100, 105, 98)
    assert (_body_size(c), _range_size(c), _upper_wick(c), _lower_wick(c)) == (
        3.0,
        7.0,
        2.0,
        2.0,
    )
    assert _is_bullish(c) is False
    assert _is_bearish(c) is True


def test_doji_has_no_body_and_no_direction():
    c = candle(100, 100, 101, 99)
    assert (_body_size(c), _range_size(c), _upper_wick(c), _lower_wick(c)) == (
        0.0,
        2.0,
        1.0,
        1.0,
    )
    assert _is_bullish(c) is False
    assert _is_bearish(c) is False


@pytest.mark.parametrize(
    "open_, close, high, low, expected",
    [
        pytest.param(100, 103, 104, 99, True, id="exact-boundaries"),
        pytest.param(100, 102.9, 103, 100, False, id="body-just-short"),
        pytest.param(100, 103, 106, 99, False, id="ratio-too-small"),
        pytest.param(103, 100, 104, 99, False, id="bearish-candle"),
        pytest.param(100, 100, 101, 99, False, id="doji"),
        pytest.param(100, 100, 100, 100, False, id="zero-range"),
        pytest.param(100, 108, 109, 99.5, True, id="large-body"),
    ],
)
def test_strong_bullish_candle(open_, close, high, low, expected):
    result = _is_strong_bullish_candle(candle(open_, close, high, low), AVERAGE_BODY)
    assert result is expected


@pytest.mark.parametrize(
    "open_, close, high, low, expected",
    [
        pytest.param(103, 100, 104, 99, True, id="exact-boundaries"),
        pytest.param(102.9, 100, 103, 100, False, id="body-just-short"),
        pytest.param(103, 100, 104, 97, False, id="ratio-too-small"),
        pytest.param(100, 103, 104, 99, False, id="bullish-candle"),
        pytest.param(100, 100, 101, 99, False, id="doji"),
        pytest.param(100, 100, 100, 100, False, id="zero-range"),
        pytest.param(108, 100, 108.5, 99, True, id="large-body"),
    ],
)
def test_strong_bearish_candle(open_, close, high, low, expected):
    result = _is_strong_bearish_candle(candle(open_, close, high, low), AVERAGE_BODY)
    assert result is expected


def build_objects():
    c = candle(100, 103, 105, 98)
    bos = BreakOfStructure(
        direction="bullish",
        broken_level=100.0,
        candle_index=3,
        candle_timestamp=T0,
    )
    brk = TrendContinuationBreak(
        direction="bullish", break_level=100.0, candle_index=3, candle=c, bos=bos
    )
    retest = TrendContinuationRetest(
        direction="bullish",
        break_level=100.0,
        break_index=3,
        retest_index=5,
        candle=c,
        bos=bos,
    )
    confirmation = TrendContinuationConfirmation(
        direction="bullish",
        confirmation_index=6,
        pattern="hammer",
        candle=c,
        retest=retest,
    )
    signal = TrendContinuationSignal(
        direction="bullish",
        entry_price=103.0,
        stop_loss=98.0,
        take_profit=None,
        break_level=100.0,
        confirmation_pattern="hammer",
        reason="test",
    )
    return brk, retest, confirmation, signal


def test_new_scope_fields_default_to_undefined():
    brk, retest, confirmation, signal = build_objects()
    assert brk.structure_scope is StructureScope.UNDEFINED
    assert retest.structure_scope is StructureScope.UNDEFINED
    assert signal.structure_scope is StructureScope.UNDEFINED
    assert confirmation.retest is retest
    assert signal.take_profit is None


def test_dataclasses_are_frozen():
    brk, retest, confirmation, signal = build_objects()
    for obj, field in (
        (brk, "break_level"),
        (retest, "retest_index"),
        (confirmation, "pattern"),
        (signal, "entry_price"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, 1)
