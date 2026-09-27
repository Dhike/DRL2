"""Propulsion Blocks: an order block retested (wick overlap into its
range) and then confirmed by a close continuing in the SAME direction
as the order block itself, past its own boundary.

Ported from ~/DRL/apps/api/app/scanner/price_action.py. Direction does
NOT flip (unlike Breaker/Reclaimed) -- this represents the order block
successfully holding and the original move resuming.
"""

from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection
from app.scanner.order_block import OrderBlock


@dataclass(frozen=True)
class PropulsionBlock:
    direction: FVGDirection
    high_price: float
    low_price: float
    open_price: float
    close_price: float
    midpoint_price: float
    order_block_candle_index: int
    interaction_candle_index: int
    confirmation_candle_index: int
    order_block: OrderBlock


def detect_propulsion_blocks(
    candles: list[Candle],
    order_blocks: tuple[OrderBlock, ...],
) -> tuple[PropulsionBlock, ...]:
    """
    Two-stage detection per order block:

    1. Interaction: the first candle whose WICK overlaps the order
       block's [low_price, high_price] range (candle.low <= high_price
       and candle.high >= low_price -- true overlap, not just a
       one-sided touch). If none found, this order block is skipped.
    2. Confirmation: after interaction, the first CLOSE continuing in
       the SAME direction as the order block, beyond its OWN boundary
       (bullish OB: close > high_price; bearish OB: close < low_price).
       Direction is unchanged from the order block's own direction.
    """
    propulsion_blocks: list[PropulsionBlock] = []

    if not candles or not order_blocks:
        return tuple()

    for order_block in order_blocks:
        start_index = order_block.candle_index + 1
        interaction_index: int | None = None

        for candle_index in range(start_index, len(candles)):
            candle = candles[candle_index]

            if (
                candle.low <= order_block.high_price
                and candle.high >= order_block.low_price
            ):
                interaction_index = candle_index
                break

        if interaction_index is None:
            continue

        for candle_index in range(interaction_index + 1, len(candles)):
            candle = candles[candle_index]

            if (
                order_block.direction == FVGDirection.BULLISH
                and candle.close > order_block.high_price
            ):
                propulsion_blocks.append(
                    PropulsionBlock(
                        direction=FVGDirection.BULLISH,
                        high_price=order_block.high_price,
                        low_price=order_block.low_price,
                        open_price=order_block.open_price,
                        close_price=order_block.close_price,
                        midpoint_price=order_block.midpoint_price,
                        order_block_candle_index=order_block.candle_index,
                        interaction_candle_index=interaction_index,
                        confirmation_candle_index=candle_index,
                        order_block=order_block,
                    )
                )
                break

            if (
                order_block.direction == FVGDirection.BEARISH
                and candle.close < order_block.low_price
            ):
                propulsion_blocks.append(
                    PropulsionBlock(
                        direction=FVGDirection.BEARISH,
                        high_price=order_block.high_price,
                        low_price=order_block.low_price,
                        open_price=order_block.open_price,
                        close_price=order_block.close_price,
                        midpoint_price=order_block.midpoint_price,
                        order_block_candle_index=order_block.candle_index,
                        interaction_candle_index=interaction_index,
                        confirmation_candle_index=candle_index,
                        order_block=order_block,
                    )
                )
                break

    return tuple(propulsion_blocks)
