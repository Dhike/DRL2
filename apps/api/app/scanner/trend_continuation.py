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

from app.scanner.confirmation import (
    Confirmation,
    _body_size,
    _is_bearish,
    _is_bearish_engulfing,
    _is_bearish_inside_bar_breakout,
    _is_bearish_marubozu,
    _is_bearish_outside_bar,
    _is_bearish_pin_bar,
    _is_bullish,
    _is_bullish_engulfing,
    _is_bullish_inside_bar_breakout,
    _is_bullish_marubozu,
    _is_bullish_outside_bar,
    _is_bullish_pin_bar,
    _is_evening_star,
    _is_falling_three_methods,
    _is_hammer,
    _is_morning_star,
    _is_rising_three_methods,
    _is_shooting_star,
    _is_three_black_crows,
    _is_three_white_soldiers,
    _lower_wick,
    _range_size,
    _upper_wick,
    detect_pattern_confirmation,
)


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


def detect_confirmation(
    candles: list[Candle],
    retest: TrendContinuationRetest,
) -> TrendContinuationConfirmation | None:
    """
    Detect an approved candlestick confirmation after the BOS retest.

    Delegates the pattern matching to the shared confirmation library so
    Trend Continuation, Break & Retest and Liquidity Sweep run the same
    candlestick checks.
    """
    result = detect_pattern_confirmation(
        candles,
        retest.direction,
        retest.break_level,
        retest.retest_index + 1,
    )

    if result is None:
        return None

    return TrendContinuationConfirmation(
        direction=result.direction,
        confirmation_index=result.confirmation_index,
        pattern=result.pattern,
        candle=result.candle,
        retest=retest,
    )

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
