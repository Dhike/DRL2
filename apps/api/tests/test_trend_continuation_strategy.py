from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.structure import (
    BreakOfStructure,
    MarketState,
    StructureLabel,
    StructureScope,
    SwingPoint,
    SwingType,
)
from app.scanner.trend_continuation import (
    TrendContinuationBreak,
    TrendContinuationSignal,
    detect_retest as detect_tc_retest,
    detect_strong_break,
    detect_trend_continuation,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
HIGH, LOW = SwingType.HIGH, SwingType.LOW
EXT, INT, UND = (
    StructureScope.EXTERNAL,
    StructureScope.INTERNAL,
    StructureScope.UNDEFINED,
)
UP, DOWN = MarketState.UPTREND, MarketState.DOWNTREND


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


def bos(direction, level, candle_index):
    return BreakOfStructure(
        direction=direction,
        broken_level=float(level),
        candle_index=candle_index,
        candle_timestamp=T0 + timedelta(hours=candle_index),
    )


def swing(index, price, kind, scope):
    return SwingPoint(
        index=index,
        timestamp=T0 + timedelta(hours=index),
        price=float(price),
        swing_type=kind,
        label=StructureLabel.HH,
        scope=scope,
    )


def make_break(direction, level, index, rows, scope=UND):
    candles = candles_from(rows)
    return candles, TrendContinuationBreak(
        direction=direction,
        break_level=float(level),
        candle_index=index,
        candle=candles[index],
        bos=bos(direction, level, index),
        structure_scope=scope,
    )


# Rows are (open, close, high, low). Small candles have body 1 and range 2.
SMALL = (100, 101, 101.5, 99.5)
ZERO = (100, 100, 100, 100)
HUGE = (100, 120, 121, 99)
BOS_BULL = (101, 105, 105.5, 100.5)
BOS_BEAR = (101, 97, 101.5, 96.5)
RETEST_UP = (104, 103, 104.5, 101.5)
RETEST_UP_LOW = (104, 103, 104.5, 99.0)
HAMMER_UP = (103.5, 104.0, 104.25, 100.0)
RETEST_DN = (96, 97, 98.5, 95.5)
RETEST_DN_HIGH = (96, 97, 101.0, 95.5)
STAR_DN = (96.5, 96.0, 100.0, 95.75)
WEAK_BODY = (101, 102.4, 102.5, 100.9)
WEAK_RATIO = (101, 104, 108, 100)

BULL_BOS = bos("bullish", 102.0, 11)
BEAR_BOS = bos("bearish", 98.0, 11)


def bull_rows(retest=RETEST_UP, confirm=HAMMER_UP):
    return [SMALL] * 11 + [BOS_BULL, retest, confirm]


def bear_rows(retest=RETEST_DN, confirm=STAR_DN):
    return [SMALL] * 11 + [BOS_BEAR, retest, confirm]


# ---- detect_strong_break -----------------------------------------------------


def test_bullish_strong_break_in_an_uptrend():
    candles = candles_from(bull_rows())
    result = detect_strong_break(candles, UP, [BULL_BOS])
    assert result is not None
    assert (result.direction, result.break_level, result.candle_index) == (
        "bullish",
        102.0,
        11,
    )
    assert result.candle == candles[11]
    assert result.bos == BULL_BOS
    assert result.structure_scope is UND


def test_bearish_strong_break_in_a_downtrend():
    candles = candles_from(bear_rows())
    result = detect_strong_break(candles, DOWN, [BEAR_BOS])
    assert result is not None
    assert (result.direction, result.break_level, result.candle_index) == (
        "bearish",
        98.0,
        11,
    )
    assert result.candle == candles[11]


@pytest.mark.parametrize(
    "rows, state, event",
    [
        pytest.param(bull_rows(), DOWN, BULL_BOS, id="downtrend-with-bullish-break"),
        pytest.param(bull_rows(), MarketState.RANGING, BULL_BOS, id="ranging"),
        pytest.param(bull_rows(), MarketState.UNDEFINED, BULL_BOS, id="undefined"),
        pytest.param(bear_rows(), UP, BEAR_BOS, id="uptrend-with-bearish-break"),
    ],
)
def test_market_state_must_match_the_break_direction(rows, state, event):
    assert detect_strong_break(candles_from(rows), state, [event]) is None


@pytest.mark.parametrize(
    "weak",
    [
        pytest.param(WEAK_BODY, id="body-just-short"),
        pytest.param(WEAK_RATIO, id="ratio-too-small"),
    ],
)
def test_weak_break_candles_are_rejected(weak):
    candles = candles_from([SMALL] * 11 + [weak])
    assert detect_strong_break(candles, UP, [BULL_BOS]) is None


def test_break_beyond_the_candles_is_skipped():
    candles = candles_from(bull_rows())
    result = detect_strong_break(candles, UP, [bos("bullish", 102.0, 50), BULL_BOS])
    assert result.candle_index == 11


@pytest.mark.parametrize(
    "rows, event",
    [
        pytest.param([BOS_BULL], bos("bullish", 102.0, 0), id="no-previous-candles"),
        pytest.param([ZERO, BOS_BULL], bos("bullish", 102.0, 1), id="only-zero-range-previous"),
    ],
)
def test_break_without_usable_previous_candles(rows, event):
    assert detect_strong_break(candles_from(rows), UP, [event]) is None


ORDER_ROWS = [SMALL] * 11 + [BOS_BULL, SMALL, SMALL, (103, 107, 107.5, 102.5)]


@pytest.mark.parametrize(
    "events, expected",
    [
        pytest.param([BULL_BOS, bos("bullish", 102.0, 14)], 11, id="older-listed-first"),
        pytest.param([bos("bullish", 102.0, 14), BULL_BOS], 14, id="newer-listed-first"),
    ],
)
def test_first_listed_break_wins(events, expected):
    result = detect_strong_break(candles_from(ORDER_ROWS), UP, events)
    assert result.candle_index == expected


def test_average_uses_only_the_last_ten_candles():
    rows = [HUGE, HUGE] + [SMALL] * 10 + [BOS_BULL]
    result = detect_strong_break(candles_from(rows), UP, [bos("bullish", 102.0, 12)])
    assert result is not None
    assert result.candle_index == 12


def test_average_ignores_zero_range_candles():
    b2 = (100, 102, 102.5, 99.5)
    rows = [ZERO, b2] * 5 + [(100, 102.5, 103, 99.8)]
    assert detect_strong_break(candles_from(rows), UP, [bos("bullish", 101.0, 10)]) is None


def test_break_carries_the_scope_of_the_broken_swing():
    candles = candles_from(bull_rows())
    result = detect_strong_break(
        candles, UP, [BULL_BOS], swings=[swing(5, 102.0, HIGH, EXT)]
    )
    assert result.structure_scope is EXT


@pytest.mark.parametrize(
    "candles, events",
    [
        pytest.param([], [BULL_BOS], id="no-candles"),
        pytest.param(candles_from(bull_rows()), [], id="no-breaks"),
    ],
)
def test_no_candles_or_no_breaks(candles, events):
    assert detect_strong_break(candles, UP, events) is None


# ---- detect_retest (Trend Continuation) --------------------------------------

RETEST_BULL_ROWS = [
    SMALL,
    SMALL,
    SMALL,
    (101, 105, 105.5, 99.5),
    (102, 103, 104, 101),
    (102, 103, 104, 100.5),
    (101, 102, 103, 100.0),
    (100, 101, 102, 99),
]
RETEST_BEAR_ROWS = [
    (100, 99, 100.5, 98.5),
    (100, 99, 100.5, 98.5),
    (100, 99, 100.5, 98.5),
    (99, 95, 100.5, 94.5),
    (98, 97, 99, 96),
    (98, 97, 99.5, 96),
    (99, 98, 100.0, 97),
    (100, 101, 102, 99),
]


def test_bullish_retest_is_the_first_candle_that_touches_the_level():
    candles, brk = make_break("bullish", 100, 3, RETEST_BULL_ROWS)
    result = detect_tc_retest(candles, brk)
    assert result is not None
    assert (result.direction, result.break_level, result.break_index) == (
        "bullish",
        100.0,
        3,
    )
    assert result.retest_index == 6


def test_bearish_retest_is_the_first_candle_that_touches_the_level():
    candles, brk = make_break("bearish", 100, 3, RETEST_BEAR_ROWS)
    result = detect_tc_retest(candles, brk)
    assert result is not None
    assert (result.direction, result.retest_index) == ("bearish", 6)


@pytest.mark.parametrize(
    "direction, rows",
    [
        pytest.param(
            "bullish",
            RETEST_BULL_ROWS[:6] + [(102, 103, 104, 101), (102, 103, 104, 101)],
            id="bullish-never-touches",
        ),
        pytest.param(
            "bearish",
            RETEST_BEAR_ROWS[:6] + [(98, 97, 99, 96), (98, 97, 99, 96)],
            id="bearish-never-touches",
        ),
    ],
)
def test_no_retest_when_the_level_is_never_touched(direction, rows):
    candles, brk = make_break(direction, 100, 3, rows)
    assert detect_tc_retest(candles, brk) is None


def test_no_retest_without_candles_after_the_break():
    candles, brk = make_break("bullish", 100, 3, RETEST_BULL_ROWS[:4])
    assert detect_tc_retest(candles, brk) is None


def test_a_candle_that_closes_beyond_the_level_still_counts():
    rows = RETEST_BULL_ROWS[:4] + [(101, 99, 101.5, 98.5)]
    candles, brk = make_break("bullish", 100, 3, rows)
    result = detect_tc_retest(candles, brk)
    assert result.retest_index == 4


def test_retest_carries_the_break_scope_and_fields():
    candles, brk = make_break("bullish", 100, 3, RETEST_BULL_ROWS, scope=EXT)
    result = detect_tc_retest(candles, brk)
    assert result.candle == candles[6]
    assert result.bos is brk.bos
    assert result.structure_scope is EXT


# ---- detect_trend_continuation -----------------------------------------------


def test_bullish_signal():
    signal = detect_trend_continuation(candles_from(bull_rows()), UP, [BULL_BOS])
    assert signal == TrendContinuationSignal(
        direction="bullish",
        entry_price=104.0,
        stop_loss=100.0,
        take_profit=None,
        break_level=102.0,
        confirmation_pattern="hammer",
        reason=(
            "Trend confirmed, strong BOS completed, BOS level retested, "
            "and hammer confirmed continuation."
        ),
        structure_scope=UND,
    )


def test_bearish_signal():
    signal = detect_trend_continuation(candles_from(bear_rows()), DOWN, [BEAR_BOS])
    assert signal == TrendContinuationSignal(
        direction="bearish",
        entry_price=96.0,
        stop_loss=100.0,
        take_profit=None,
        break_level=98.0,
        confirmation_pattern="shooting_star",
        reason=(
            "Trend confirmed, strong BOS completed, BOS level retested, "
            "and shooting_star confirmed continuation."
        ),
        structure_scope=UND,
    )


@pytest.mark.parametrize(
    "rows, state, event, stop",
    [
        pytest.param(bull_rows(retest=RETEST_UP_LOW), UP, BULL_BOS, 99.0, id="bullish-stop-from-retest-low"),
        pytest.param(bear_rows(retest=RETEST_DN_HIGH), DOWN, BEAR_BOS, 101.0, id="bearish-stop-from-retest-high"),
    ],
)
def test_stop_loss_uses_the_more_extreme_of_retest_and_confirmation(rows, state, event, stop):
    signal = detect_trend_continuation(candles_from(rows), state, [event])
    assert signal.stop_loss == stop


def test_too_few_candles_gives_no_signal():
    candles = candles_from(bull_rows()[:4])
    assert detect_trend_continuation(candles, UP, [BULL_BOS]) is None


@pytest.mark.parametrize("state", [MarketState.RANGING, MarketState.UNDEFINED])
def test_no_signal_without_a_trend(state):
    assert detect_trend_continuation(candles_from(bull_rows()), state, [BULL_BOS]) is None


def test_no_signal_without_breaks():
    assert detect_trend_continuation(candles_from(bull_rows()), UP, []) is None


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param([SMALL] * 11 + [WEAK_BODY, RETEST_UP, HAMMER_UP], id="no-strong-break"),
        pytest.param(
            [SMALL] * 11 + [BOS_BULL, (104, 105, 105.5, 103), (105, 106, 106.5, 104)],
            id="no-retest",
        ),
        pytest.param(bull_rows(confirm=(103, 103.2, 103.6, 102.8)), id="no-confirmation"),
    ],
)
def test_no_signal_when_a_stage_is_missing(rows):
    assert detect_trend_continuation(candles_from(rows), UP, [BULL_BOS]) is None


@pytest.mark.parametrize("scope", [EXT, INT, UND])
def test_signal_scope_comes_from_the_broken_swing(scope):
    signal = detect_trend_continuation(
        candles_from(bull_rows()),
        UP,
        [BULL_BOS],
        swings=[swing(5, 102.0, HIGH, scope)],
    )
    assert signal.structure_scope is scope


@pytest.mark.parametrize(
    "swings",
    [
        pytest.param(None, id="no-swings"),
        pytest.param([swing(5, 101.9, HIGH, EXT)], id="price-does-not-match"),
        pytest.param([swing(5, 102.0, LOW, EXT)], id="wrong-swing-type"),
    ],
)
def test_signal_scope_is_undefined_without_a_matching_swing(swings):
    signal = detect_trend_continuation(
        candles_from(bull_rows()), UP, [BULL_BOS], swings=swings
    )
    assert signal.structure_scope is UND


@pytest.mark.parametrize(
    "scope, swings, expect_signal",
    [
        pytest.param(EXT, [swing(5, 102.0, HIGH, EXT)], True, id="matching-scope"),
        pytest.param(EXT, [swing(5, 102.0, HIGH, INT)], False, id="other-scope"),
        pytest.param(EXT, None, False, id="scope-unknown"),
        pytest.param(None, [swing(5, 102.0, HIGH, INT)], True, id="no-filter"),
    ],
)
def test_scope_filter(scope, swings, expect_signal):
    signal = detect_trend_continuation(
        candles_from(bull_rows()), UP, [BULL_BOS], swings=swings, scope=scope
    )
    assert (signal is not None) is expect_signal
