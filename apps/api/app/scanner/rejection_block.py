"""Rejection Blocks: single-candle wick rejections (a pin-bar-style
signal) -- no mitigation, no BOS or order block dependency.

Ported from ~/DRL/apps/api/app/scanner/price_action.py.
"""

from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection


@dataclass(frozen=True)
class RejectionBlock:
    direction: FVGDirection
    high_price: float
    low_price: float
    open_price: float
    close_price: float
    midpoint_price: float
    candle_index: int


def detect_rejection_blocks(candles: list[Candle]) -> tuple[RejectionBlock, ...]:
    """Detect bullish and bearish rejection blocks from a single candle's
    wick-to-body structure.

    Bullish: a bullish candle (close>open) with a lower wick at least
    2x the body and at least 40% of the full range.
    Bearish: a bearish candle (close<open) with an upper wick at least
    2x the body and at least 40% of the full range.
    Zero-range candles are skipped.
    """
    rejection_blocks: list[RejectionBlock] = []

    for candle_index, candle in enumerate(candles):
        candle_range = candle.high - candle.low
        if candle_range <= 0:
            continue

        body = abs(candle.close - candle.open)
        lower_wick = min(candle.open, candle.close) - candle.low
        upper_wick = candle.high - max(candle.open, candle.close)

        if (
            candle.close > candle.open
            and lower_wick >= body * 2
            and lower_wick >= candle_range * 0.40
        ):
            midpoint = (candle.high + candle.low) / 2
            rejection_blocks.append(
                RejectionBlock(
                    direction=FVGDirection.BULLISH,
                    high_price=candle.high,
                    low_price=candle.low,
                    open_price=candle.open,
                    close_price=candle.close,
                    midpoint_price=midpoint,
                    candle_index=candle_index,
                )
            )
        elif (
            candle.close < candle.open
            and upper_wick >= body * 2
            and upper_wick >= candle_range * 0.40
        ):
            midpoint = (candle.high + candle.low) / 2
            rejection_blocks.append(
                RejectionBlock(
                    direction=FVGDirection.BEARISH,
                    high_price=candle.high,
                    low_price=candle.low,
                    open_price=candle.open,
                    close_price=candle.close,
                    midpoint_price=midpoint,
                    candle_index=candle_index,
                )
            )

    return tuple(rejection_blocks)
