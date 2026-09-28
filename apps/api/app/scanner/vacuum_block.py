"""Vacuum Blocks: a strong displacement candle that leaves a price gap
against the immediately preceding candle -- the LAST of the 9 POI types.

Ported from ~/DRL/apps/api/app/scanner/price_action.py. Combines a
strong-candle check (same 1.5x-average-body and 60%-body-ratio shape as
Trend Continuation's detect_strong_break) with a two-candle gap check
against only the immediately preceding candle (unlike FVG's
three-candle rule).
"""

from dataclasses import dataclass, replace

from app.market.models import Candle
from app.scanner.fair_value_gap import FVGDirection, FVGState


@dataclass(frozen=True)
class VacuumBlock:
    direction: FVGDirection
    high_price: float
    low_price: float
    previous_candle_index: int
    displacement_candle_index: int
    displacement_open_price: float
    displacement_high_price: float
    displacement_low_price: float
    displacement_close_price: float
    state: FVGState = FVGState.ACTIVE
    mitigation_candle_index: int | None = None


def detect_vacuum_blocks(candles: list[Candle]) -> tuple[VacuumBlock, ...]:
    """
    Detect vacuum blocks: a strong displacement candle (body >= 1.5x the
    average body of the 10 preceding candles, and body/range >= 0.60)
    whose move leaves a price gap against the IMMEDIATELY PRECEDING
    candle's opposite extreme.

    Bullish: displacement closes up, and the previous candle's high is
    below the displacement's own low (a gap up).
    Bearish: displacement closes down, and the previous candle's low is
    above the displacement's own high (a gap down).

    Needs at least 11 candles (10 lookback + the displacement candle).
    """
    vacuum_blocks: list[VacuumBlock] = []

    if len(candles) < 11:
        return tuple()

    for candle_index in range(10, len(candles)):
        displacement = candles[candle_index]
        previous = candles[candle_index - 1]

        displacement_range = displacement.high - displacement.low
        if displacement_range <= 0:
            continue

        displacement_body = abs(displacement.close - displacement.open)
        if displacement_body <= 0:
            continue

        previous_candles = candles[candle_index - 10 : candle_index]
        total_body = sum(abs(c.close - c.open) for c in previous_candles)
        average_body = total_body / 10
        if average_body <= 0:
            continue

        if displacement_body < average_body * 1.5:
            continue

        body_ratio = displacement_body / displacement_range
        if body_ratio < 0.60:
            continue

        if displacement.close > displacement.open and previous.high < displacement.low:
            vacuum_blocks.append(
                VacuumBlock(
                    direction=FVGDirection.BULLISH,
                    high_price=displacement.low,
                    low_price=previous.high,
                    previous_candle_index=candle_index - 1,
                    displacement_candle_index=candle_index,
                    displacement_open_price=displacement.open,
                    displacement_high_price=displacement.high,
                    displacement_low_price=displacement.low,
                    displacement_close_price=displacement.close,
                )
            )
        elif displacement.close < displacement.open and previous.low > displacement.high:
            vacuum_blocks.append(
                VacuumBlock(
                    direction=FVGDirection.BEARISH,
                    high_price=previous.low,
                    low_price=displacement.high,
                    previous_candle_index=candle_index - 1,
                    displacement_candle_index=candle_index,
                    displacement_open_price=displacement.open,
                    displacement_high_price=displacement.high,
                    displacement_low_price=displacement.low,
                    displacement_close_price=displacement.close,
                )
            )

    return tuple(vacuum_blocks)


def detect_vacuum_block_mitigation(
    candles: list[Candle], vacuum_block: VacuumBlock
) -> VacuumBlock:
    """Mark an active vacuum block as mitigated once a candle's wick
    overlaps its [low_price, high_price] zone, recording where."""
    if vacuum_block.state != FVGState.ACTIVE:
        return vacuum_block

    start_index = vacuum_block.displacement_candle_index + 1

    for candle_index in range(start_index, len(candles)):
        candle = candles[candle_index]
        if candle.low <= vacuum_block.high_price and candle.high >= vacuum_block.low_price:
            return replace(
                vacuum_block,
                state=FVGState.MITIGATED,
                mitigation_candle_index=candle_index,
            )

    return vacuum_block
