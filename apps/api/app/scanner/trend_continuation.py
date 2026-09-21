from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.structure import (
    BreakOfStructure,
    MarketState,
    StructureScope,
    SwingPoint,
    SwingType,
)


@dataclass(frozen=True)
class TrendContinuationBreak:
    direction: str
    break_level: float
    candle_index: int
    candle: Candle
    bos: BreakOfStructure
    structure_scope: StructureScope = StructureScope.UNDEFINED


@dataclass(frozen=True)
class TrendContinuationRetest:
    direction: str
    break_level: float
    break_index: int
    retest_index: int
    candle: Candle
    bos: BreakOfStructure
    structure_scope: StructureScope = StructureScope.UNDEFINED


@dataclass(frozen=True)
class TrendContinuationConfirmation:
    direction: str
    confirmation_index: int
    pattern: str
    candle: Candle
    retest: TrendContinuationRetest


@dataclass(frozen=True)
class TrendContinuationSignal:
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float | None
    break_level: float
    confirmation_pattern: str
    reason: str
    structure_scope: StructureScope = StructureScope.UNDEFINED


def _body_size(candle: Candle) -> float:
    return abs(candle.close - candle.open)


def _range_size(candle: Candle) -> float:
    return candle.high - candle.low


def _upper_wick(candle: Candle) -> float:
    return candle.high - max(candle.open, candle.close)


def _lower_wick(candle: Candle) -> float:
    return min(candle.open, candle.close) - candle.low


def _is_bullish(candle: Candle) -> bool:
    return candle.close > candle.open


def _is_bearish(candle: Candle) -> bool:
    return candle.close < candle.open


def _is_strong_bullish_candle(
    candle: Candle,
    average_body: float,
) -> bool:
    candle_range = _range_size(candle)

    if candle_range <= 0:
        return False

    body = _body_size(candle)

    return (
        _is_bullish(candle)
        and body >= average_body * 1.5
        and body / candle_range >= 0.60
    )


def _is_strong_bearish_candle(
    candle: Candle,
    average_body: float,
) -> bool:
    candle_range = _range_size(candle)

    if candle_range <= 0:
        return False

    body = _body_size(candle)

    return (
        _is_bearish(candle)
        and body >= average_body * 1.5
        and body / candle_range >= 0.60
    )


def _is_bullish_pin_bar(
    candle: Candle,
    level: float,
) -> bool:
    candle_range = _range_size(candle)
    body = _body_size(candle)

    if candle_range <= 0 or body <= 0:
        return False

    lower_wick = _lower_wick(candle)
    upper_wick = _upper_wick(candle)

    return (
        candle.low <= level
        and candle.close > level
        and _is_bullish(candle)
        and lower_wick >= body * 2.0
        and lower_wick > upper_wick
        and body / candle_range <= 0.40
    )


def _is_bearish_pin_bar(
    candle: Candle,
    level: float,
) -> bool:
    candle_range = _range_size(candle)
    body = _body_size(candle)

    if candle_range <= 0 or body <= 0:
        return False

    upper_wick = _upper_wick(candle)
    lower_wick = _lower_wick(candle)

    return (
        candle.high >= level
        and candle.close < level
        and _is_bearish(candle)
        and upper_wick >= body * 2.0
        and upper_wick > lower_wick
        and body / candle_range <= 0.40
    )


def _is_bullish_engulfing(
    previous: Candle,
    candle: Candle,
    level: float,
) -> bool:
    if not (_is_bearish(previous) and _is_bullish(candle)):
        return False

    return (
        candle.low <= level
        and candle.close > level
        and candle.open <= previous.close
        and candle.close >= previous.open
        and _body_size(candle) > _body_size(previous)
    )


def _is_bearish_engulfing(
    previous: Candle,
    candle: Candle,
    level: float,
) -> bool:
    if not (_is_bullish(previous) and _is_bearish(candle)):
        return False

    return (
        candle.high >= level
        and candle.close < level
        and candle.open >= previous.close
        and candle.close <= previous.open
        and _body_size(candle) > _body_size(previous)
    )


def _is_bullish_outside_bar(
    previous: Candle,
    candle: Candle,
    level: float,
) -> bool:
    return (
        _is_bullish(candle)
        and candle.high > previous.high
        and candle.low < previous.low
        and candle.close > level
    )


def _is_bearish_outside_bar(
    previous: Candle,
    candle: Candle,
    level: float,
) -> bool:
    return (
        _is_bearish(candle)
        and candle.high > previous.high
        and candle.low < previous.low
        and candle.close < level
    )


def _is_bullish_marubozu(
    candle: Candle,
    level: float,
) -> bool:
    candle_range = _range_size(candle)
    body = _body_size(candle)

    if candle_range <= 0:
        return False

    return (
        _is_bullish(candle)
        and candle.low <= level
        and candle.close > level
        and body / candle_range >= 0.85
    )


def _is_bearish_marubozu(
    candle: Candle,
    level: float,
) -> bool:
    candle_range = _range_size(candle)
    body = _body_size(candle)

    if candle_range <= 0:
        return False

    return (
        _is_bearish(candle)
        and candle.high >= level
        and candle.close < level
        and body / candle_range >= 0.85
    )


def _is_hammer(
    candle: Candle,
    level: float,
) -> bool:
    candle_range = _range_size(candle)
    body = _body_size(candle)

    if candle_range <= 0 or body <= 0:
        return False

    lower_wick = _lower_wick(candle)
    upper_wick = _upper_wick(candle)
    body_midpoint = (candle.open + candle.close) / 2

    return (
        _is_bullish(candle)
        and candle.low <= level
        and candle.close > level
        and lower_wick >= body * 2.0
        and upper_wick <= body
        and body_midpoint >= candle.low + candle_range * 0.60
    )


def _is_shooting_star(
    candle: Candle,
    level: float,
) -> bool:
    candle_range = _range_size(candle)
    body = _body_size(candle)

    if candle_range <= 0 or body <= 0:
        return False

    upper_wick = _upper_wick(candle)
    lower_wick = _lower_wick(candle)
    body_midpoint = (candle.open + candle.close) / 2

    return (
        _is_bearish(candle)
        and candle.high >= level
        and candle.close < level
        and upper_wick >= body * 2.0
        and lower_wick <= body
        and body_midpoint <= candle.low + candle_range * 0.40
    )


def _is_morning_star(
    candles: list[Candle],
    index: int,
    level: float,
) -> bool:
    if index < 2:
        return False

    first = candles[index - 2]
    middle = candles[index - 1]
    third = candles[index]

    first_body = _body_size(first)
    middle_body = _body_size(middle)

    if first_body <= 0:
        return False

    midpoint = (first.open + first.close) / 2

    return (
        _is_bearish(first)
        and middle_body <= first_body * 0.50
        and _is_bullish(third)
        and third.close > midpoint
        and third.close > level
        and third.low <= level
    )


def _is_evening_star(
    candles: list[Candle],
    index: int,
    level: float,
) -> bool:
    if index < 2:
        return False

    first = candles[index - 2]
    middle = candles[index - 1]
    third = candles[index]

    first_body = _body_size(first)
    middle_body = _body_size(middle)

    if first_body <= 0:
        return False

    midpoint = (first.open + first.close) / 2

    return (
        _is_bullish(first)
        and middle_body <= first_body * 0.50
        and _is_bearish(third)
        and third.close < midpoint
        and third.close < level
        and third.high >= level
    )


def _is_three_white_soldiers(
    candles: list[Candle],
    index: int,
    level: float,
) -> bool:
    if index < 2:
        return False

    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]

    return (
        _is_bullish(first)
        and _is_bullish(second)
        and _is_bullish(third)
        and second.close > first.close
        and third.close > second.close
        and second.open > first.open
        and third.open > second.open
        and third.close > level
        and third.low <= level
    )


def _is_three_black_crows(
    candles: list[Candle],
    index: int,
    level: float,
) -> bool:
    if index < 2:
        return False

    first = candles[index - 2]
    second = candles[index - 1]
    third = candles[index]

    return (
        _is_bearish(first)
        and _is_bearish(second)
        and _is_bearish(third)
        and second.close < first.close
        and third.close < second.close
        and second.open < first.open
        and third.open < second.open
        and third.close < level
        and third.high >= level
    )


def _is_rising_three_methods(
    candles: list[Candle],
    index: int,
    level: float,
) -> bool:
    if index < 4:
        return False

    first = candles[index - 4]
    second = candles[index - 3]
    third = candles[index - 2]
    fourth = candles[index - 1]
    fifth = candles[index]

    first_body = _body_size(first)
    fifth_body = _body_size(fifth)

    if first_body <= 0 or fifth_body <= 0:
        return False

    return (
        _is_bullish(first)
        and _is_bearish(second)
        and _is_bearish(third)
        and _is_bearish(fourth)
        and second.high < first.high
        and third.high < first.high
        and fourth.high < first.high
        and second.low > first.low
        and third.low > first.low
        and fourth.low > first.low
        and _is_bullish(fifth)
        and fifth.close > first.high
        and fifth.close > level
        and fifth_body >= first_body * 0.50
    )


def _is_falling_three_methods(
    candles: list[Candle],
    index: int,
    level: float,
) -> bool:
    if index < 4:
        return False

    first = candles[index - 4]
    second = candles[index - 3]
    third = candles[index - 2]
    fourth = candles[index - 1]
    fifth = candles[index]

    first_body = _body_size(first)
    fifth_body = _body_size(fifth)

    if first_body <= 0 or fifth_body <= 0:
        return False

    return (
        _is_bearish(first)
        and _is_bullish(second)
        and _is_bullish(third)
        and _is_bullish(fourth)
        and second.high < first.high
        and third.high < first.high
        and fourth.high < first.high
        and second.low > first.low
        and third.low > first.low
        and fourth.low > first.low
        and _is_bearish(fifth)
        and fifth.close < first.low
        and fifth.close < level
        and fifth_body >= first_body * 0.50
    )


def _is_bullish_inside_bar_breakout(
    candles: list[Candle],
    index: int,
    level: float,
) -> bool:
    if index < 2:
        return False

    mother = candles[index - 2]
    inside = candles[index - 1]
    breakout = candles[index]

    return (
        inside.high <= mother.high
        and inside.low >= mother.low
        and _is_bullish(breakout)
        and breakout.close > mother.high
        and breakout.close > level
    )


def _is_bearish_inside_bar_breakout(
    candles: list[Candle],
    index: int,
    level: float,
) -> bool:
    if index < 2:
        return False

    mother = candles[index - 2]
    inside = candles[index - 1]
    breakout = candles[index]

    return (
        inside.high <= mother.high
        and inside.low >= mother.low
        and _is_bearish(breakout)
        and breakout.close < mother.low
        and breakout.close < level
    )


def detect_confirmation(
    candles: list[Candle],
    retest: TrendContinuationRetest,
) -> TrendContinuationConfirmation | None:
    """
    Detect an approved candlestick confirmation after the BOS retest.

    The pattern must:
        - occur after the retest,
        - respect the BOS level,
        - agree with the trend direction,
        - and produce a directional close.

    Pattern priority:
        1. Hammer / Shooting Star
        2. Pin Bar
        3. Marubozu
        4. Outside Bar
        5. Engulfing
        6. Multi-candle confirmations
    """
    start_index = retest.retest_index + 1

    for candle_index in range(
        start_index,
        len(candles),
    ):
        candle = candles[candle_index]

        if retest.direction == "bullish":
            if _is_hammer(
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="hammer",
                    candle=candle,
                    retest=retest,
                )

            if _is_bullish_pin_bar(
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="bullish_pin_bar",
                    candle=candle,
                    retest=retest,
                )

            if _is_bullish_marubozu(
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="bullish_marubozu",
                    candle=candle,
                    retest=retest,
                )

            if candle_index >= 1 and _is_bullish_outside_bar(
                candles[candle_index - 1],
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="bullish_outside_bar",
                    candle=candle,
                    retest=retest,
                )

            if candle_index >= 1 and _is_bullish_engulfing(
                candles[candle_index - 1],
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="bullish_engulfing",
                    candle=candle,
                    retest=retest,
                )

            if _is_morning_star(
                candles,
                candle_index,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="morning_star",
                    candle=candle,
                    retest=retest,
                )

            if _is_three_white_soldiers(
                candles,
                candle_index,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="three_white_soldiers",
                    candle=candle,
                    retest=retest,
                )

            if _is_rising_three_methods(
                candles,
                candle_index,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="rising_three_methods",
                    candle=candle,
                    retest=retest,
                )

            if _is_bullish_inside_bar_breakout(
                candles,
                candle_index,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bullish",
                    confirmation_index=candle_index,
                    pattern="bullish_inside_bar_breakout",
                    candle=candle,
                    retest=retest,
                )

        elif retest.direction == "bearish":
            if _is_shooting_star(
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="shooting_star",
                    candle=candle,
                    retest=retest,
                )

            if _is_bearish_pin_bar(
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="bearish_pin_bar",
                    candle=candle,
                    retest=retest,
                )

            if _is_bearish_marubozu(
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="bearish_marubozu",
                    candle=candle,
                    retest=retest,
                )

            if candle_index >= 1 and _is_bearish_outside_bar(
                candles[candle_index - 1],
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="bearish_outside_bar",
                    candle=candle,
                    retest=retest,
                )

            if candle_index >= 1 and _is_bearish_engulfing(
                candles[candle_index - 1],
                candle,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="bearish_engulfing",
                    candle=candle,
                    retest=retest,
                )

            if _is_evening_star(
                candles,
                candle_index,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="evening_star",
                    candle=candle,
                    retest=retest,
                )

            if _is_three_black_crows(
                candles,
                candle_index,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="three_black_crows",
                    candle=candle,
                    retest=retest,
                )

            if _is_falling_three_methods(
                candles,
                candle_index,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="falling_three_methods",
                    candle=candle,
                    retest=retest,
                )

            if _is_bearish_inside_bar_breakout(
                candles,
                candle_index,
                retest.break_level,
            ):
                return TrendContinuationConfirmation(
                    direction="bearish",
                    confirmation_index=candle_index,
                    pattern="bearish_inside_bar_breakout",
                    candle=candle,
                    retest=retest,
                )

    return None


def _find_broken_swing(
    swings: list[SwingPoint],
    bos: BreakOfStructure,
) -> SwingPoint | None:
    candidates = [
        swing
        for swing in swings
        if swing.label is not None
        and swing.index < bos.candle_index
        and swing.price == bos.broken_level
        and (
            (bos.direction == "bullish" and swing.swing_type == SwingType.HIGH)
            or (bos.direction == "bearish" and swing.swing_type == SwingType.LOW)
        )
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda swing: swing.index)


def _scope_of_break(
    swings: list[SwingPoint] | None,
    bos: BreakOfStructure,
) -> StructureScope:
    if not swings:
        return StructureScope.UNDEFINED

    broken = _find_broken_swing(swings, bos)

    if broken is None:
        return StructureScope.UNDEFINED

    return broken.scope


def detect_strong_break(
    candles: list[Candle],
    market_state: MarketState,
    bos_events: list[BreakOfStructure],
    swings: list[SwingPoint] | None = None,
    scope: StructureScope | None = None,
) -> TrendContinuationBreak | None:
    if not candles or not bos_events:
        return None

    for bos in bos_events:
        if bos.candle_index >= len(candles):
            continue

        candle = candles[bos.candle_index]

        lookback_start = max(0, bos.candle_index - 10)
        previous_candles = candles[
            lookback_start:bos.candle_index
        ]

        bodies = [
            _body_size(previous)
            for previous in previous_candles
            if _range_size(previous) > 0
        ]

        if not bodies:
            continue

        average_body = sum(bodies) / len(bodies)

        break_scope = _scope_of_break(swings, bos)

        if scope is not None and break_scope != scope:
            continue

        if (
            market_state == MarketState.UPTREND
            and bos.direction == "bullish"
            and _is_strong_bullish_candle(
                candle,
                average_body,
            )
        ):
            return TrendContinuationBreak(
                direction="bullish",
                break_level=bos.broken_level,
                candle_index=bos.candle_index,
                candle=candle,
                bos=bos,
                structure_scope=break_scope,
            )

        if (
            market_state == MarketState.DOWNTREND
            and bos.direction == "bearish"
            and _is_strong_bearish_candle(
                candle,
                average_body,
            )
        ):
            return TrendContinuationBreak(
                direction="bearish",
                break_level=bos.broken_level,
                candle_index=bos.candle_index,
                candle=candle,
                bos=bos,
                structure_scope=break_scope,
            )

    return None


def detect_retest(
    candles: list[Candle],
    strong_break: TrendContinuationBreak,
) -> TrendContinuationRetest | None:
    start_index = strong_break.candle_index + 1

    for candle_index in range(
        start_index,
        len(candles),
    ):
        candle = candles[candle_index]

        if strong_break.direction == "bullish":
            if candle.low <= strong_break.break_level:
                return TrendContinuationRetest(
                    direction="bullish",
                    break_level=strong_break.break_level,
                    break_index=strong_break.candle_index,
                    retest_index=candle_index,
                    candle=candle,
                    bos=strong_break.bos,
                    structure_scope=strong_break.structure_scope,
                )

        elif strong_break.direction == "bearish":
            if candle.high >= strong_break.break_level:
                return TrendContinuationRetest(
                    direction="bearish",
                    break_level=strong_break.break_level,
                    break_index=strong_break.candle_index,
                    retest_index=candle_index,
                    candle=candle,
                    bos=strong_break.bos,
                    structure_scope=strong_break.structure_scope,
                )

    return None


def detect_trend_continuation(
    candles: list[Candle],
    market_state: MarketState,
    bos_events: list[BreakOfStructure],
    swings: list[SwingPoint] | None = None,
    scope: StructureScope | None = None,
) -> TrendContinuationSignal | None:
    """
    Trend Continuation sequence:

    1. Confirm overall trend.
    2. Use verified BOS.
    3. Require a strong directional BOS candle.
    4. Wait for a retest of the broken level.
    5. Require an approved candlestick confirmation pattern.
    6. Produce the strategy signal.

    Risk management and final order execution remain outside this
    strategy engine.
    """

    if len(candles) < 5:
        return None

    if market_state not in (
        MarketState.UPTREND,
        MarketState.DOWNTREND,
    ):
        return None

    strong_break = detect_strong_break(
        candles=candles,
        market_state=market_state,
        bos_events=bos_events,
        swings=swings,
        scope=scope,
    )

    if strong_break is None:
        return None

    retest = detect_retest(
        candles=candles,
        strong_break=strong_break,
    )

    if retest is None:
        return None

    confirmation = detect_confirmation(
        candles=candles,
        retest=retest,
    )

    if confirmation is None:
        return None

    candle = confirmation.candle

    if confirmation.direction == "bullish":
        entry_price = candle.close
        stop_loss = min(
            retest.candle.low,
            candle.low,
        )
    else:
        entry_price = candle.close
        stop_loss = max(
            retest.candle.high,
            candle.high,
        )

    return TrendContinuationSignal(
        direction=confirmation.direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=None,
        break_level=retest.break_level,
        confirmation_pattern=confirmation.pattern,
        reason=(
            "Trend confirmed, strong BOS completed, "
            "BOS level retested, and "
            f"{confirmation.pattern} confirmed continuation."
        ),
        structure_scope=retest.structure_scope,
    )
