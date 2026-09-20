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
