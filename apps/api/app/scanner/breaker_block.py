"""Breaker Blocks: an order block invalidated by a CLOSE through its
opposite boundary, flipping its directional role.

Ported from ~/DRL/apps/api/app/scanner/price_action.py.
"""

from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection
from app.scanner.order_block import OrderBlock


@dataclass(frozen=True)
class BreakerBlock:
    direction: FVGDirection
    high_price: float
    low_price: float
    open_price: float
    close_price: float
    midpoint_price: float
    order_block_candle_index: int
    invalidation_candle_index: int
    order_block: OrderBlock


def detect_breaker_blocks(
    candles: list[Candle],
    order_blocks: tuple[OrderBlock, ...],
) -> tuple[BreakerBlock, ...]:
    """Detect breaker blocks: an order block invalidated by the first
    CLOSE (not wick) beyond its opposite boundary.

    A bearish order block invalidated by a close above its high becomes
    a bullish breaker; a bullish order block invalidated by a close
    below its low becomes a bearish breaker. Stops at the first
    invalidating candle for each order block.
    """
    breaker_blocks: list[BreakerBlock] = []

    if not candles or not order_blocks:
        return tuple()

    for order_block in order_blocks:
        start_index = order_block.candle_index + 1

        for candle_index in range(start_index, len(candles)):
            candle = candles[candle_index]

            if (
                order_block.direction == FVGDirection.BEARISH
                and candle.close > order_block.high_price
            ):
                breaker_blocks.append(
                    BreakerBlock(
                        direction=FVGDirection.BULLISH,
                        high_price=order_block.high_price,
                        low_price=order_block.low_price,
                        open_price=order_block.open_price,
                        close_price=order_block.close_price,
                        midpoint_price=order_block.midpoint_price,
                        order_block_candle_index=order_block.candle_index,
                        invalidation_candle_index=candle_index,
                        order_block=order_block,
                    )
                )
                break

            if (
                order_block.direction == FVGDirection.BULLISH
                and candle.close < order_block.low_price
            ):
                breaker_blocks.append(
                    BreakerBlock(
                        direction=FVGDirection.BEARISH,
                        high_price=order_block.high_price,
                        low_price=order_block.low_price,
                        open_price=order_block.open_price,
                        close_price=order_block.close_price,
                        midpoint_price=order_block.midpoint_price,
                        order_block_candle_index=order_block.candle_index,
                        invalidation_candle_index=candle_index,
                        order_block=order_block,
                    )
                )
                break

    return tuple(breaker_blocks)
