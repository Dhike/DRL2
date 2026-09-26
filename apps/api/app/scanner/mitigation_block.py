"""Mitigation Blocks: a record of WHERE an already-mitigated order
block's mitigation actually occurred.

Ported from ~/DRL/apps/api/app/scanner/price_action.py. Only considers
order blocks whose state is already MITIGATED, then re-locates the
first candle that returned into the block's range -- same condition as
detect_order_block_mitigation, but producing an event record rather
than mutating state. Keeps the SAME direction as the source order
block (unlike Breaker Blocks, which flip direction).
"""

from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection, FVGState
from app.scanner.order_block import OrderBlock


@dataclass(frozen=True)
class MitigationBlock:
    direction: FVGDirection
    high_price: float
    low_price: float
    open_price: float
    close_price: float
    midpoint_price: float
    order_block_candle_index: int
    mitigation_candle_index: int
    order_block: OrderBlock


def detect_mitigation_blocks(
    candles: list[Candle],
    order_blocks: tuple[OrderBlock, ...],
) -> tuple[MitigationBlock, ...]:
    """Detect mitigation blocks from order blocks that have already been
    mitigated. Skips any order block whose state is not MITIGATED."""
    mitigation_blocks: list[MitigationBlock] = []

    if not candles or not order_blocks:
        return tuple()

    for order_block in order_blocks:
        if order_block.state != FVGState.MITIGATED:
            continue

        start_index = order_block.candle_index + 1

        for candle_index in range(start_index, len(candles)):
            candle = candles[candle_index]

            if (
                order_block.direction == FVGDirection.BULLISH
                and candle.low <= order_block.high_price
            ):
                mitigation_blocks.append(
                    MitigationBlock(
                        direction=FVGDirection.BULLISH,
                        high_price=order_block.high_price,
                        low_price=order_block.low_price,
                        open_price=order_block.open_price,
                        close_price=order_block.close_price,
                        midpoint_price=order_block.midpoint_price,
                        order_block_candle_index=order_block.candle_index,
                        mitigation_candle_index=candle_index,
                        order_block=order_block,
                    )
                )
                break

            if (
                order_block.direction == FVGDirection.BEARISH
                and candle.high >= order_block.low_price
            ):
                mitigation_blocks.append(
                    MitigationBlock(
                        direction=FVGDirection.BEARISH,
                        high_price=order_block.high_price,
                        low_price=order_block.low_price,
                        open_price=order_block.open_price,
                        close_price=order_block.close_price,
                        midpoint_price=order_block.midpoint_price,
                        order_block_candle_index=order_block.candle_index,
                        mitigation_candle_index=candle_index,
                        order_block=order_block,
                    )
                )
                break

    return tuple(mitigation_blocks)
