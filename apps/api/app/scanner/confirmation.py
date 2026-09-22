"""Shared candlestick confirmation patterns.

Used by Trend Continuation, Break & Retest and Liquidity Sweep as the
final confirmation stage. Pure functions over plain candles, a direction
and a price level -- no strategy-specific dataclasses -- so every
strategy can call the same code.
"""

from dataclasses import dataclass

from app.market.models import Candle


@dataclass(frozen=True)
class Confirmation:
    direction: str
    confirmation_index: int
    pattern: str
    candle: Candle


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




def detect_pattern_confirmation(
    candles: list[Candle],
    direction: str,
    level: float,
    start_index: int,
) -> Confirmation | None:
    """
    Detect an approved candlestick confirmation from `start_index` onward.

    Pattern priority:
        1. Hammer / Shooting Star
        2. Pin Bar
        3. Marubozu
        4. Outside Bar
        5. Engulfing
        6. Multi-candle confirmations
    """
    for candle_index in range(start_index, len(candles)):
        candle = candles[candle_index]

        if direction == "bullish":
            if _is_hammer(candle, level):
                return Confirmation("bullish", candle_index, "hammer", candle)
            if _is_bullish_pin_bar(candle, level):
                return Confirmation("bullish", candle_index, "bullish_pin_bar", candle)
            if _is_bullish_marubozu(candle, level):
                return Confirmation("bullish", candle_index, "bullish_marubozu", candle)
            if candle_index >= 1 and _is_bullish_outside_bar(
                candles[candle_index - 1], candle, level
            ):
                return Confirmation("bullish", candle_index, "bullish_outside_bar", candle)
            if candle_index >= 1 and _is_bullish_engulfing(
                candles[candle_index - 1], candle, level
            ):
                return Confirmation("bullish", candle_index, "bullish_engulfing", candle)
            if _is_morning_star(candles, candle_index, level):
                return Confirmation("bullish", candle_index, "morning_star", candle)
            if _is_three_white_soldiers(candles, candle_index, level):
                return Confirmation("bullish", candle_index, "three_white_soldiers", candle)
            if _is_rising_three_methods(candles, candle_index, level):
                return Confirmation("bullish", candle_index, "rising_three_methods", candle)
            if _is_bullish_inside_bar_breakout(candles, candle_index, level):
                return Confirmation(
                    "bullish", candle_index, "bullish_inside_bar_breakout", candle
                )

        elif direction == "bearish":
            if _is_shooting_star(candle, level):
                return Confirmation("bearish", candle_index, "shooting_star", candle)
            if _is_bearish_pin_bar(candle, level):
                return Confirmation("bearish", candle_index, "bearish_pin_bar", candle)
            if _is_bearish_marubozu(candle, level):
                return Confirmation("bearish", candle_index, "bearish_marubozu", candle)
            if candle_index >= 1 and _is_bearish_outside_bar(
                candles[candle_index - 1], candle, level
            ):
                return Confirmation("bearish", candle_index, "bearish_outside_bar", candle)
            if candle_index >= 1 and _is_bearish_engulfing(
                candles[candle_index - 1], candle, level
            ):
                return Confirmation("bearish", candle_index, "bearish_engulfing", candle)
            if _is_evening_star(candles, candle_index, level):
                return Confirmation("bearish", candle_index, "evening_star", candle)
            if _is_three_black_crows(candles, candle_index, level):
                return Confirmation("bearish", candle_index, "three_black_crows", candle)
            if _is_falling_three_methods(candles, candle_index, level):
                return Confirmation("bearish", candle_index, "falling_three_methods", candle)
            if _is_bearish_inside_bar_breakout(candles, candle_index, level):
                return Confirmation(
                    "bearish", candle_index, "bearish_inside_bar_breakout", candle
                )

    return None
