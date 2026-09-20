from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.break_and_retest import (
    BreakAndRetestState,
    detect_break_and_retest,
    detect_retest,
)
from app.scanner.structure import (
    BreakOfStructure,
    StructureLabel,
    StructureScope,
    SwingPoint,
    SwingType,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
HIGH, LOW = SwingType.HIGH, SwingType.LOW
EXT, INT, UND = (
    StructureScope.EXTERNAL,
    StructureScope.INTERNAL,
    StructureScope.UNDEFINED,
)
STATE = BreakAndRetestState


def candles_from(rows):
    """Each row is (low, high, close); open equals close."""
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=float(close),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=1.0,
        )
        for i, (low, high, close) in enumerate(rows)
    ]


def swing(index, price, kind, scope, label=StructureLabel.HH):
    return SwingPoint(
        index=index,
        timestamp=BASE + timedelta(hours=index),
        price=float(price),
        swing_type=kind,
        label=label,
        scope=scope,
    )


def bos(direction, level, candle_index):
    return BreakOfStructure(
        direction=direction,
        broken_level=float(level),
        candle_index=candle_index,
        candle_timestamp=BASE + timedelta(hours=candle_index),
    )


# Level 100, break candle is index 3. Index 6 closes below the level (touch but
# no hold), index 7 touches and closes exactly on the level (the retest).
RETEST_ROWS_BULLISH = [
    (95, 97, 96),
    (96, 99, 98),
    (97, 99, 98),
    (98, 106, 105),
    (103, 108, 107),
    (104, 109, 108),
    (98.5, 106, 99.0),
    (100, 105, 100),
    (98, 104, 103),
]

# Mirror image: index 6 closes above the level, index 7 touches and closes on it.
RETEST_ROWS_BEARISH = [
    (103, 105, 104),
    (102, 104, 103),
    (102, 104, 103),
    (94, 102, 95),
    (91, 96, 92),
    (90, 95, 91),
    (94, 101.5, 101.0),
    (92, 100, 100),
    (93, 101, 96),
]

# Bullish break of a swing high at 100 (break candle 4, retest candle 6).
BASE_ROWS = [
    (94, 96, 95),
    (95, 97, 96),
    (97, 100, 98),
    (96, 99, 97),
    (97, 104, 103),
    (102, 106, 105),
    (100, 105, 101),
    (104, 108, 107),
    (97, 101, 99),
    (98, 102, 99.5),
    (99, 103, 99),
    (94, 100, 95),
]
NO_RETEST_TAIL = [(91, 94, 92), (90, 93, 91)]
RETEST_TAIL = [(91, 94, 92), (93, 97, 96)]

S_A_ROWS = BASE_ROWS[:8]
S_B_ROWS = [
    (103, 105, 104),
    (102, 104, 103),
    (100, 103, 101),
    (101, 104, 102),
    (96, 103, 97),
    (94, 98, 95),
    (95, 100, 99),
]

H2 = swing(2, 100, HIGH, EXT)
L8 = swing(8, 97, LOW, INT, label=StructureLabel.HL)
L2_BEARISH = swing(2, 100, LOW, INT, label=StructureLabel.HL)
BOS1 = bos("bullish", 100, 4)
BOS2 = bos("bearish", 97, 11)
BOS_BEARISH = bos("bearish", 100, 4)


def long_rows(retest_for_first_break, tail):
    rows = list(BASE_ROWS)
    if not retest_for_first_break:
        rows[6] = (103, 107, 106)
    return rows + tail


# ---- detect_retest -----------------------------------------------------------


def test_bullish_retest_is_the_first_candle_that_touches_and_holds():
    candles = candles_from(RETEST_ROWS_BULLISH)
    event = bos("bullish", 100, 3)
    result = detect_retest(candles, event, EXT)
    assert result is not None
    assert (
        result.direction,
        result.break_level,
        result.break_index,
        result.retest_index,
    ) == ("bullish", 100.0, 3, 7)
    assert result.candle == candles[7]
    assert result.bos == event
    assert result.structure_scope is EXT


def test_bearish_retest_is_the_first_candle_that_touches_and_holds():
    candles = candles_from(RETEST_ROWS_BEARISH)
    event = bos("bearish", 100, 3)
    result = detect_retest(candles, event, INT)
    assert result is not None
    assert (
        result.direction,
        result.break_level,
        result.break_index,
        result.retest_index,
    ) == ("bearish", 100.0, 3, 7)
    assert result.candle == candles[7]
    assert result.structure_scope is INT


def test_only_candles_after_the_break_count():
    rows = [
        (95, 97, 96),
        (96, 99, 98),
        (99, 104, 101),
        (98, 106, 105),
        (103, 108, 107),
        (104, 109, 108),
    ]
    assert detect_retest(candles_from(rows), bos("bullish", 100, 3), EXT) is None


@pytest.mark.parametrize(
    "candles, event",
    [
        ([], bos("bullish", 100, 3)),
        (candles_from(RETEST_ROWS_BULLISH), bos("bullish", 100, 9)),
        (candles_from(RETEST_ROWS_BULLISH), bos("bullish", 100, -1)),
        (candles_from(RETEST_ROWS_BULLISH), bos("neutral", 100, 3)),
    ],
)
def test_retest_guards(candles, event):
    assert detect_retest(candles, event, EXT) is None


# ---- detect_break_and_retest -------------------------------------------------


def test_bullish_setup_waits_for_confirmation():
    candles = candles_from(S_A_ROWS)
    result = detect_break_and_retest(candles, [H2], [BOS1])
    assert result.state is STATE.WAITING_FOR_BULLISH_CONFIRMATION
    setup = result.setup
    assert (
        setup.direction,
        setup.break_level,
        setup.break_index,
        setup.retest_index,
    ) == ("bullish", 100.0, 4, 6)
    assert setup.break_timestamp == candles[4].timestamp
    assert setup.retest_timestamp == candles[6].timestamp
    assert setup.structure_scope is EXT
    assert setup.bos == BOS1
    assert setup.retest.candle == candles[6]
    assert setup.retest.structure_scope is EXT


def test_bearish_setup_waits_for_confirmation():
    candles = candles_from(S_B_ROWS)
    result = detect_break_and_retest(candles, [L2_BEARISH], [BOS_BEARISH])
    assert result.state is STATE.WAITING_FOR_BEARISH_CONFIRMATION
    setup = result.setup
    assert (
        setup.direction,
        setup.break_level,
        setup.break_index,
        setup.retest_index,
    ) == ("bearish", 100.0, 4, 6)
    assert setup.structure_scope is INT


@pytest.mark.parametrize("scope", [EXT, INT, UND])
def test_scope_comes_from_the_broken_swing(scope):
    broken = swing(2, 100, HIGH, scope)
    result = detect_break_and_retest(candles_from(S_A_ROWS), [broken], [BOS1])
    assert result.setup.structure_scope is scope
    assert result.setup.retest.structure_scope is scope


def test_waits_for_a_bullish_retest_when_price_has_not_returned():
    rows = list(S_A_ROWS)
    rows[6] = (103, 107, 106)
    result = detect_break_and_retest(candles_from(rows), [H2], [BOS1])
    assert result.state is STATE.WAITING_FOR_BULLISH_RETEST
    assert result.setup is None


def test_waits_for_a_bearish_retest_when_price_has_not_returned():
    rows = list(S_B_ROWS)
    rows[6] = (91, 96, 92)
    result = detect_break_and_retest(
        candles_from(rows), [L2_BEARISH], [BOS_BEARISH]
    )
    assert result.state is STATE.WAITING_FOR_BEARISH_RETEST
    assert result.setup is None


@pytest.mark.parametrize(
    "candles, swings, events",
    [
        ([], [H2], [BOS1]),
        (candles_from(S_A_ROWS), [], [BOS1]),
        (candles_from(S_A_ROWS), [H2], []),
    ],
)
def test_waiting_for_break_without_inputs(candles, swings, events):
    result = detect_break_and_retest(candles, swings, events)
    assert result.state is STATE.WAITING_FOR_BREAK
    assert result.setup is None


@pytest.mark.parametrize(
    "broken",
    [
        swing(2, 100, HIGH, EXT, label=None),
        swing(2, 101, HIGH, EXT),
        swing(4, 100, HIGH, EXT),
        swing(2, 100, LOW, EXT),
    ],
)
def test_waiting_for_break_when_no_swing_matches_the_break(broken):
    result = detect_break_and_retest(candles_from(S_A_ROWS), [broken], [BOS1])
    assert result.state is STATE.WAITING_FOR_BREAK
    assert result.setup is None


def test_latest_break_with_a_retest_wins():
    candles = candles_from(long_rows(True, RETEST_TAIL))
    result = detect_break_and_retest(candles, [H2, L8], [BOS1, BOS2])
    assert result.state is STATE.WAITING_FOR_BEARISH_CONFIRMATION
    setup = result.setup
    assert (setup.direction, setup.break_index, setup.retest_index) == (
        "bearish",
        11,
        13,
    )
    assert setup.structure_scope is INT


def test_falls_back_to_an_older_break_that_has_a_retest():
    candles = candles_from(long_rows(True, NO_RETEST_TAIL))
    result = detect_break_and_retest(candles, [H2, L8], [BOS1, BOS2])
    assert result.state is STATE.WAITING_FOR_BULLISH_CONFIRMATION
    setup = result.setup
    assert (setup.direction, setup.break_index, setup.retest_index) == (
        "bullish",
        4,
        6,
    )


def test_no_retest_for_any_break_uses_the_latest_breaks_direction():
    candles = candles_from(long_rows(False, NO_RETEST_TAIL))
    result = detect_break_and_retest(candles, [H2, L8], [BOS1, BOS2])
    assert result.state is STATE.WAITING_FOR_BEARISH_RETEST
    assert result.setup is None


def test_results_do_not_leak_between_calls():
    first = detect_break_and_retest(candles_from(S_A_ROWS), [H2], [BOS1])
    other = detect_break_and_retest(
        candles_from(S_B_ROWS), [L2_BEARISH], [BOS_BEARISH]
    )
    again = detect_break_and_retest(candles_from(S_A_ROWS), [H2], [BOS1])
    assert other.state is STATE.WAITING_FOR_BEARISH_CONFIRMATION
    assert first == again
