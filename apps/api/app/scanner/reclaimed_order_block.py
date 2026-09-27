"""Reclaimed Order Blocks: an order block invalidated by a close beyond
its boundary (same condition as Breaker Block), then later RECLAIMED
by a close landing back inside its own high/low range.

Ported from ~/DRL/apps/api/app/scanner/price_action.py.
"""

from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection
from app.scanner.order_block import OrderBlock


@dataclass(frozen=True)
class ReclaimedOrderBlock:
    direction: FVGDirection
    high_price: float
    low_price: float
    open_price: float
    close_price: float
    midpoint_price: float
    order_block_candle_index: int
    invalidation_candle_index: int
    reclaim_candle_index: int
    order_block: OrderBlock


def detect_reclaimed_order_blocks(
    candles: list[Candle],
    order_blocks: tuple[OrderBlock, ...],
) -> tuple[ReclaimedOrderBlock, ...]:
    """
    Two-stage detection per order block:

    1. Invalidation: same as Breaker Block -- the first CLOSE beyond
       the opposite boundary (bearish OB: close > high; bullish OB:
       close < low). If none found, this order block is skipped.
    2. Reclaim: after invalidation, the first CLOSE that lands back
       INSIDE the order block's own [low_price, high_price] range
       (inclusive both ends). The direction flips, same as Breaker
       Block (bearish OB -> bullish reclaim; bullish OB -> bearish
       reclaim).
    """
    reclaimed_blocks: list[ReclaimedOrderBlock] = []

    if not candles or not order_blocks:
        return tuple()

    for order_block in order_blocks:
        start_index = order_block.candle_index + 1
        invalidation_index: int | None = None

        for candle_index in range(start_index, len(candles)):
            candle = candles[candle_index]

            if (
                order_block.direction == FVGDirection.BEARISH
                and candle.close > order_block.high_price
            ):
                invalidation_index = candle_index
                break
            if (
                order_block.direction == FVGDirection.BULLISH
                and candle.close < order_block.low_price
            ):
                invalidation_index = candle_index
                break

        if invalidation_index is None:
            continue

        for candle_index in range(invalidation_index + 1, len(candles)):
            candle = candles[candle_index]

            if order_block.direction == FVGDirection.BEARISH and (
                order_block.low_price <= candle.close <= order_block.high_price
            ):
                reclaimed_blocks.append(
                    ReclaimedOrderBlock(
                        direction=FVGDirection.BULLISH,
                        high_price=order_block.high_price,
                        low_price=order_block.low_price,
                        open_price=order_block.open_price,
                        close_price=order_block.close_price,
                        midpoint_price=order_block.midpoint_price,
                        order_block_candle_index=order_block.candle_index,
                        invalidation_candle_index=invalidation_index,
                        reclaim_candle_index=candle_index,
                        order_block=order_block,
                    )
                )
                break

            if order_block.direction == FVGDirection.BULLISH and (
                order_block.low_price <= candle.close <= order_block.high_price
            ):
                reclaimed_blocks.append(
                    ReclaimedOrderBlock(
                        direction=FVGDirection.BEARISH,
                        high_price=order_block.high_price,
                        low_price=order_block.low_price,
                        open_price=order_block.open_price,
                        close_price=order_block.close_price,
                        midpoint_price=order_block.midpoint_price,
                        order_block_candle_index=order_block.candle_index,
                        invalidation_candle_index=invalidation_index,
                        reclaim_candle_index=candle_index,
                        order_block=order_block,
                    )
                )
                break

    return tuple(reclaimed_blocks)
