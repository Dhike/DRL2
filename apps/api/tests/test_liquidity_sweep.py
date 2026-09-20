from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.liquidity_sweep import (
    LiquidityLevel,
    LiquiditySweep,
    detect_liquidity_levels,
    detect_liquidity_returns,
    detect_liquidity_sweeps,
    detect_post_choch_bos,
)
from app.scanner.structure import (
    ChangeOfCharacter,
    MarketState,
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


def candles_from_rows(rows):
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


def candles_from_closes(closes):
    return candles_from_rows([(c - 0.5, c + 0.5, c) for c in closes])


def swing(index, price, kind, scope=UND, label=StructureLabel.HH):
    return SwingPoint(
        index=index,
        timestamp=BASE + timedelta(hours=index),
        price=float(price),
        swing_type=kind,
        label=label,
        scope=scope,
    )


def level(side, price, swing_index, scope=UND):
    return LiquidityLevel(
        side=side, price=float(price), swing_index=swing_index, scope=scope
    )


def choch(direction, candle_index):
    previous = MarketState.DOWNTREND if direction == "bullish" else MarketState.UPTREND
    return ChangeOfCharacter(
        direction=direction,
        broken_level=100.0,
        candle_index=candle_index,
        candle_timestamp=BASE + timedelta(hours=candle_index),
        previous_direction=previous,
    )


def summary(sweeps):
    return [(s.side, s.liquidity_price, s.candle_index, s.swing_index) for s in sweeps]


# Buy-side level 110 (swing 2): index 4 has an equal high, index 5 sweeps.
S1_ROWS = [
    (95, 100, 98),
    (96, 105, 100),
    (100, 110, 105),
    (101, 109, 106),
    (102, 110, 107),
    (103, 111, 104),
    (104, 112, 105),
]

# Sell-side level 90 (swing 2): index 4 has an equal low, index 5 sweeps.
S2_ROWS = [
    (95, 100, 98),
    (93, 99, 95),
    (90, 96, 93),
    (91, 97, 95),
    (90, 96, 92),
    (89, 95, 90),
    (88, 94, 90),
]

# Buy-side level 110 (swing 4): earlier and same-candle highs are ignored.
S3_ROWS = [
    (95, 100, 98),
    (96, 101, 99),
    (100, 115, 105),
    (99, 104, 100),
    (100, 111, 105),
    (101, 109, 106),
    (102, 112, 107),
]

# One wide candle (index 3) exceeds both levels at 110 and 90 (swing 1).
S4_ROWS = [
    (95, 100, 98),
    (91, 110, 100),
    (92, 105, 100),
    (88, 112, 100),
]

# Buy-side sweep at index 5; price trades back to 110 at index 7 (equal low).
R1_ROWS = [
    (95, 100, 98),
    (96, 101, 99),
    (100, 110, 105),
    (101, 109, 106),
    (102, 110, 107),
    (103, 111, 104),
    (111, 113, 112),
    (110, 114, 112),
    (105, 112, 108),
]

# Sell-side sweep at index 5; price trades back to 90 at index 7 (equal high).
R2_ROWS = [
    (95, 100, 98),
    (93, 99, 95),
    (90, 96, 93),
    (91, 97, 95),
    (90, 96, 92),
    (89, 95, 90),
    (86, 89, 88),
    (87, 90, 89),
    (88, 94, 92),
]

# Same sweep as R1 but no later candle ever trades back down to 110.
R3_ROWS = R1_ROWS[:6] + [(111, 113, 112), (111, 114, 113)]


# ---- detect_liquidity_levels -------------------------------------------------


def test_highs_are_buy_side_and_lows_are_sell_side():
    candles = candles_from_rows(S1_ROWS)
    swings = (swing(2, 110, HIGH, label=None), swing(4, 95, LOW))
    levels = detect_liquidity_levels(candles, swings)
    assert [(l.side, l.price, l.swing_index) for l in levels] == [
        ("buy_side", 110.0, 2),
        ("sell_side", 95.0, 4),
    ]


def test_swings_beyond_the_candles_are_skipped():
    candles = candles_from_rows(S1_ROWS[:5])
    swings = (swing(4, 95, LOW), swing(5, 110, HIGH), swing(9, 120, HIGH))
    levels = detect_liquidity_levels(candles, swings)
    assert [(l.side, l.swing_index) for l in levels] == [("sell_side", 4)]


def test_levels_carry_the_swing_scope():
    candles = candles_from_rows(S1_ROWS)
    levels = detect_liquidity_levels(candles, (swing(2, 110, HIGH, EXT),))
    assert levels[0].scope is EXT


@pytest.mark.parametrize(
    "scope, expected",
    [(EXT, [2]), (INT, [4]), (UND, [6]), (None, [2, 4, 6])],
)
def test_scope_filter_keeps_only_matching_swings(scope, expected):
    candles = candles_from_rows(S1_ROWS)
    swings = (
        swing(2, 110, HIGH, EXT),
        swing(4, 95, LOW, INT),
        swing(6, 112, HIGH, UND),
    )
    levels = detect_liquidity_levels(candles, swings, scope=scope)
    assert [l.swing_index for l in levels] == expected


# ---- detect_liquidity_sweeps -------------------------------------------------


def test_buy_side_sweep_needs_a_high_strictly_above_the_level():
    candles = candles_from_rows(S1_ROWS)
    sweeps = detect_liquidity_sweeps(candles, (level("buy_side", 110, 2),))
    assert summary(sweeps) == [("buy_side", 110.0, 5, 2)]
    assert sweeps[0].candle == candles[5]


def test_sell_side_sweep_needs_a_low_strictly_below_the_level():
    candles = candles_from_rows(S2_ROWS)
    sweeps = detect_liquidity_sweeps(candles, (level("sell_side", 90, 2),))
    assert summary(sweeps) == [("sell_side", 90.0, 5, 2)]
    assert sweeps[0].candle == candles[5]


def test_candles_up_to_the_swing_are_ignored():
    candles = candles_from_rows(S3_ROWS)
    sweeps = detect_liquidity_sweeps(candles, (level("buy_side", 110, 4),))
    assert summary(sweeps) == [("buy_side", 110.0, 6, 4)]


def test_one_candle_can_sweep_several_levels_in_level_order():
    candles = candles_from_rows(S4_ROWS)
    levels = (level("buy_side", 110, 1), level("sell_side", 90, 1))
    sweeps = detect_liquidity_sweeps(candles, levels)
    assert summary(sweeps) == [("buy_side", 110.0, 3, 1), ("sell_side", 90.0, 3, 1)]


@pytest.mark.parametrize(
    "rows, lvl",
    [
        (S1_ROWS, level("buy_side", 120, 2)),
        (S2_ROWS, level("sell_side", 80, 2)),
    ],
)
def test_no_sweep_when_the_level_is_never_exceeded(rows, lvl):
    assert detect_liquidity_sweeps(candles_from_rows(rows), (lvl,)) == ()


@pytest.mark.parametrize(
    "candles, levels",
    [
        ([], (level("buy_side", 110, 2),)),
        (candles_from_rows(S1_ROWS), ()),
    ],
)
def test_no_levels_or_candles_no_sweeps(candles, levels):
    assert detect_liquidity_sweeps(candles, levels) == ()


def test_sweeps_carry_the_level_scope():
    candles = candles_from_rows(S1_ROWS)
    sweeps = detect_liquidity_sweeps(candles, (level("buy_side", 110, 2, INT),))
    assert sweeps[0].scope is INT


# ---- detect_post_choch_bos ---------------------------------------------------

# Verified in the structure tests: bullish break at candle 3, bearish at 6.
CHOCH_CLOSES = [100, 105, 108, 111, 112, 104, 99, 98]
CHOCH_SWINGS = [
    swing(1, 110, HIGH),
    swing(5, 100, LOW, label=StructureLabel.HL),
]


@pytest.mark.parametrize(
    "direction, expected",
    [("bullish", ("bullish", 110.0, 3)), ("bearish", ("bearish", 100.0, 6))],
)
def test_post_choch_bos_is_the_first_same_direction_break_after_the_choch(
    direction, expected
):
    result = detect_post_choch_bos(
        candles_from_closes(CHOCH_CLOSES), CHOCH_SWINGS, choch(direction, 2)
    )
    assert (result.direction, result.broken_level, result.candle_index) == expected


@pytest.mark.parametrize("direction, choch_index", [("bullish", 3), ("bearish", 6)])
def test_post_choch_bos_ignores_the_choch_candle_itself(direction, choch_index):
    result = detect_post_choch_bos(
        candles_from_closes(CHOCH_CLOSES),
        CHOCH_SWINGS,
        choch(direction, choch_index),
    )
    assert result is None


def test_post_choch_bos_without_breaks():
    assert (
        detect_post_choch_bos(candles_from_closes(CHOCH_CLOSES), [], choch("bullish", 2))
        is None
    )


# ---- detect_liquidity_returns ------------------------------------------------


def make_sweep(side, price, candles, candle_index, swing_index, scope=UND):
    return LiquiditySweep(
        side=side,
        liquidity_price=float(price),
        candle_index=candle_index,
        candle=candles[candle_index],
        swing_index=swing_index,
        scope=scope,
    )


def test_buy_side_return_when_price_trades_back_to_the_level():
    candles = candles_from_rows(R1_ROWS)
    sweep = make_sweep("buy_side", 110, candles, 5, 2)
    returns = detect_liquidity_returns(candles, (sweep,))
    assert len(returns) == 1
    result = returns[0]
    assert (result.side, result.liquidity_price) == ("buy_side", 110.0)
    assert (result.sweep_index, result.return_index) == (5, 7)
    assert result.candle == candles[7]
    assert result.sweep == sweep


def test_sell_side_return_when_price_trades_back_to_the_level():
    candles = candles_from_rows(R2_ROWS)
    sweep = make_sweep("sell_side", 90, candles, 5, 2)
    returns = detect_liquidity_returns(candles, (sweep,))
    assert len(returns) == 1
    assert (returns[0].sweep_index, returns[0].return_index) == (5, 7)
    assert returns[0].candle == candles[7]


def test_the_sweep_candle_itself_is_not_a_return():
    candles = candles_from_rows(R3_ROWS)
    sweep = make_sweep("buy_side", 110, candles, 5, 2)
    assert detect_liquidity_returns(candles, (sweep,)) == ()


def test_swings_to_returns_pipeline_keeps_the_scope():
    candles = candles_from_rows(S1_ROWS)
    levels = detect_liquidity_levels(candles, (swing(2, 110, HIGH, EXT),))
    sweeps = detect_liquidity_sweeps(candles, levels)
    returns = detect_liquidity_returns(candles, sweeps)
    assert (levels[0].scope, sweeps[0].scope, returns[0].scope) == (EXT, EXT, EXT)
    assert (sweeps[0].candle_index, returns[0].return_index) == (5, 6)
