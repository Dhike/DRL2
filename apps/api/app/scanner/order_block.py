"""Order Blocks: the last opposite-direction candle before a BOS
displacement.

Ported from ~/DRL/apps/api/app/scanner/price_action.py. Reuses
FVGDirection/FVGState from the FVG module (the old code shared these
enums across POI types) and BreakOfStructure from the structure engine.
"""

from dataclasses import dataclass, replace

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection, FVGState
from app.scanner.structure import BreakOfStructure


@dataclass(frozen=True)
class OrderBlock:
    direction: FVGDirection
    high_price: float
    low_price: float
    open_price: float
    close_price: float
    midpoint_price: float
    candle_index: int
    bos: BreakOfStructure
    state: FVGState = FVGState.ACTIVE


def detect_order_blocks(
    candles: list[Candle],
    bos_events: tuple[BreakOfStructure, ...],
) -> tuple[OrderBlock, ...]:
    """Detect core bullish and bearish order blocks validated by BOS.

    For each BOS, search backward from the BOS candle for the nearest
    OPPOSITE-color candle: a bearish candle before a bullish BOS, or a
    bullish candle before a bearish BOS. The first one found (closest
    to the BOS) is the order block; the search stops there.
    """
    order_blocks: list[OrderBlock] = []

    if not candles or not bos_events:
        return tuple()

    for bos in bos_events:
        bos_index = bos.candle_index

        if bos_index <= 0 or bos_index >= len(candles):
            continue

        for candle_index in range(bos_index - 1, -1, -1):
            candle = candles[candle_index]

            if bos.direction == "bullish":
                if candle.close >= candle.open:
                    continue
                direction = FVGDirection.BULLISH
            elif bos.direction == "bearish":
                if candle.close <= candle.open:
                    continue
                direction = FVGDirection.BEARISH
            else:
                continue

            midpoint = (candle.high + candle.low) / 2
            order_blocks.append(
                OrderBlock(
                    direction=direction,
                    high_price=candle.high,
                    low_price=candle.low,
                    open_price=candle.open,
                    close_price=candle.close,
                    midpoint_price=midpoint,
                    candle_index=candle_index,
                    bos=bos,
                )
            )
            break

    return tuple(order_blocks)


def detect_order_block_mitigation(
    candles: list[Candle], order_block: OrderBlock
) -> OrderBlock:
    """Mark an active order block as mitigated once price wicks back into
    its high/low range."""
    if order_block.state != FVGState.ACTIVE:
        return order_block

    start_index = order_block.candle_index + 1

    for candle in candles[start_index:]:
        if (
            order_block.direction == FVGDirection.BULLISH
            and candle.low <= order_block.high_price
        ):
            return replace(order_block, state=FVGState.MITIGATED)
        if (
            order_block.direction == FVGDirection.BEARISH
            and candle.high >= order_block.low_price
        ):
            return replace(order_block, state=FVGState.MITIGATED)

    return order_block
