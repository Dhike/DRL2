"""Balanced Price Range (BPR): overlapping opposite-direction Fair
Value Gaps, formed in sequence.

Ported from ~/DRL/apps/api/app/scanner/price_action.py. Pure
price-range math over already-detected FairValueGap objects -- no
candle iteration.
"""

from dataclasses import dataclass

from app.scanner.fair_value_gap import FairValueGap, FVGDirection, FVGState


@dataclass(frozen=True)
class BalancedPriceRange:
    lower_price: float
    upper_price: float
    bullish_fvg: FairValueGap
    bearish_fvg: FairValueGap


def detect_bprs(gaps: tuple[FairValueGap, ...]) -> tuple[BalancedPriceRange, ...]:
    """Detect overlapping bullish and bearish FVGs formed in sequence.

    Skips: same-direction pairs, pairs sharing the same third_candle_index
    (the same triplet's own contradictory reading), and pairs whose price
    ranges do not genuinely overlap.
    """
    bprs: list[BalancedPriceRange] = []

    for first_index, first in enumerate(gaps):
        for second in gaps[first_index + 1 :]:
            if first.direction == second.direction:
                continue

            if first.third_candle_index == second.third_candle_index:
                continue

            lower_price = max(first.lower_price, second.lower_price)
            upper_price = min(first.upper_price, second.upper_price)

            if lower_price >= upper_price:
                continue

            if first.direction == FVGDirection.BULLISH:
                bullish, bearish = first, second
            else:
                bullish, bearish = second, first

            bprs.append(
                BalancedPriceRange(
                    lower_price=lower_price,
                    upper_price=upper_price,
                    bullish_fvg=bullish,
                    bearish_fvg=bearish,
                )
            )

    return tuple(bprs)


def get_fvg_role(fvg: FairValueGap) -> FVGDirection:
    """Return the FVG's current directional role: its original direction,
    or the opposite once it has been inverted."""
    if fvg.state == FVGState.INVERTED:
        if fvg.direction == FVGDirection.BULLISH:
            return FVGDirection.BEARISH
        return FVGDirection.BULLISH

    return fvg.direction
