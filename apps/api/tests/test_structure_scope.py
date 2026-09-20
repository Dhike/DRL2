from datetime import datetime, timedelta, timezone

from app.scanner.structure import (
    BreakOfStructure,
    StructureLabel,
    StructureScope,
    SwingPoint,
    SwingType,
    classify_structure_scope,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
HIGH, LOW = SwingType.HIGH, SwingType.LOW
EXT, INT, UND = (
    StructureScope.EXTERNAL,
    StructureScope.INTERNAL,
    StructureScope.UNDEFINED,
)


def swing(index, price, kind, label=None):
    return SwingPoint(
        index=index,
        timestamp=BASE + timedelta(hours=index),
        price=float(price),
        swing_type=kind,
        label=label,
    )


def bos(direction, level, candle_index):
    return BreakOfStructure(
        direction=direction,
        broken_level=float(level),
        candle_index=candle_index,
        candle_timestamp=BASE + timedelta(hours=candle_index),
    )


def scopes(swings, events):
    result = classify_structure_scope([], swings, events)
    return [(s.index, s.scope) for s in result]


BULLISH_SWINGS = [
    swing(2, 95, LOW),
    swing(4, 110, HIGH),
    swing(6, 100, LOW),
    swing(9, 104, LOW),
    swing(11, 108, HIGH),
    swing(13, 106, LOW),
    swing(15, 115, HIGH),
    swing(17, 111, LOW),
    swing(19, 113, HIGH),
]

BEARISH_SWINGS = [
    swing(2, 120, HIGH),
    swing(4, 100, LOW),
    swing(6, 110, HIGH),
    swing(9, 106, HIGH),
    swing(11, 102, LOW),
    swing(13, 104, HIGH),
    swing(15, 95, LOW),
    swing(17, 99, HIGH),
    swing(19, 97, LOW),
]

EXPECTED_TREND_SCOPES = [
    (2, UND),
    (4, EXT),
    (6, EXT),
    (9, INT),
    (11, INT),
    (13, EXT),
    (15, EXT),
    (17, INT),
    (19, INT),
]


def test_no_swings_gives_an_empty_tuple():
    assert classify_structure_scope([], [], [bos("bullish", 110, 7)]) == ()


def test_without_breaks_everything_is_undefined_and_data_is_kept():
    swings = [
        swing(2, 95, LOW, StructureLabel.HL),
        swing(4, 110, HIGH, StructureLabel.HH),
    ]
    result = classify_structure_scope([], swings, [])
    assert isinstance(result, tuple)
    assert [s.scope for s in result] == [UND, UND]
    assert [
        (s.index, s.timestamp, s.price, s.swing_type, s.label) for s in result
    ] == [(s.index, s.timestamp, s.price, s.swing_type, s.label) for s in swings]


def test_bullish_scope_classification():
    assert scopes(BULLISH_SWINGS, [bos("bullish", 110, 7)]) == EXPECTED_TREND_SCOPES


def test_bearish_scope_classification():
    assert scopes(BEARISH_SWINGS, [bos("bearish", 100, 7)]) == EXPECTED_TREND_SCOPES


def test_swings_before_the_break_only_get_anchor_scopes():
    swings = BULLISH_SWINGS[:3]
    assert scopes(swings, [bos("bullish", 110, 7)]) == [(2, UND), (4, EXT), (6, EXT)]


def test_swing_on_the_breaking_candle_is_skipped():
    swings = [
        swing(2, 95, LOW),
        swing(4, 110, HIGH),
        swing(6, 100, LOW),
        swing(7, 101, LOW),
        swing(9, 104, LOW),
    ]
    assert scopes(swings, [bos("bullish", 110, 7)]) == [
        (2, UND),
        (4, EXT),
        (6, EXT),
        (7, UND),
        (9, INT),
    ]


def test_bearish_swing_on_the_breaking_candle_is_skipped():
    swings = [
        swing(2, 120, HIGH),
        swing(4, 100, LOW),
        swing(6, 110, HIGH),
        swing(7, 108, HIGH),
        swing(9, 106, HIGH),
    ]
    assert scopes(swings, [bos("bearish", 100, 7)]) == [
        (2, UND),
        (4, EXT),
        (6, EXT),
        (7, UND),
        (9, INT),
    ]


def test_no_external_high_means_later_highs_are_internal():
    swings = [
        swing(2, 95, LOW),
        swing(4, 110, HIGH),
        swing(6, 100, LOW),
        swing(9, 104, LOW),
        swing(11, 200, HIGH),
    ]
    assert scopes(swings, [bos("bullish", 999, 7)]) == [
        (2, UND),
        (4, UND),
        (6, EXT),
        (9, INT),
        (11, INT),
    ]


def test_no_external_low_means_later_lows_are_internal():
    swings = [
        swing(2, 120, HIGH),
        swing(4, 100, LOW),
        swing(6, 110, HIGH),
        swing(9, 106, HIGH),
        swing(11, 10, LOW),
    ]
    assert scopes(swings, [bos("bearish", 999, 7)]) == [
        (2, UND),
        (4, UND),
        (6, EXT),
        (9, INT),
        (11, INT),
    ]


def test_unknown_break_direction_leaves_everything_undefined():
    result = scopes(BULLISH_SWINGS, [bos("neutral", 110, 7)])
    assert all(scope is UND for _, scope in result)


def test_only_the_latest_break_is_used():
    events = [bos("bearish", 95, 3), bos("bullish", 110, 7)]
    assert scopes(BULLISH_SWINGS, events) == EXPECTED_TREND_SCOPES
