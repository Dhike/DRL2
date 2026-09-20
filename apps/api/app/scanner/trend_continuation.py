from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.structure import (
    BreakOfStructure,
    MarketState,
    StructureScope,
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
