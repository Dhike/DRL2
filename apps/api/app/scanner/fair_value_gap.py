"""Fair Value Gaps (FVG): the foundational POI (point of interest)
concept the rest of price-action analysis builds on.

Ported from the old ~/DRL/apps/api/app/scanner/price_action.py, adapted
to this repo's Candle (app.market.models) in place of the old
app.market_data.models.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

from app.market.models import Candle


class FVGDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class FVGState(StrEnum):
    ACTIVE = "active"
    MITIGATED = "mitigated"
    INVERTED = "inverted"


@dataclass(frozen=True)
class FairValueGap:
    direction: FVGDirection
    lower_price: float
    upper_price: float
    first_candle_index: int
    middle_candle_index: int
    third_candle_index: int
    state: FVGState = FVGState.ACTIVE


def detect_fair_value_gaps(candles: list[Candle]) -> tuple[FairValueGap, ...]:
    """Detect standard three-candle bullish and bearish FVGs.

    Bullish: candle 1's high is below candle 3's low (a gap up).
    Bearish: candle 1's low is above candle 3's high (a gap down).
    """
    gaps: list[FairValueGap] = []

    if len(candles) < 3:
        return tuple()

    for index in range(2, len(candles)):
        first = candles[index - 2]
        third = candles[index]

        if first.high < third.low:
            gaps.append(
                FairValueGap(
                    direction=FVGDirection.BULLISH,
                    lower_price=first.high,
                    upper_price=third.low,
                    first_candle_index=index - 2,
                    middle_candle_index=index - 1,
                    third_candle_index=index,
                )
            )
        elif first.low > third.high:
            gaps.append(
                FairValueGap(
                    direction=FVGDirection.BEARISH,
                    lower_price=third.high,
                    upper_price=first.low,
                    first_candle_index=index - 2,
                    middle_candle_index=index - 1,
                    third_candle_index=index,
                )
            )

    return tuple(gaps)


def detect_fvg_mitigation(candles: list[Candle], fvg: FairValueGap) -> FairValueGap:
    """Mark an active FVG as mitigated once price wicks back into its gap."""
    if fvg.state != FVGState.ACTIVE:
        return fvg

    start_index = fvg.third_candle_index + 1

    for candle in candles[start_index:]:
        if fvg.direction == FVGDirection.BULLISH and candle.low <= fvg.upper_price:
            return replace(fvg, state=FVGState.MITIGATED)
        if fvg.direction == FVGDirection.BEARISH and candle.high >= fvg.lower_price:
            return replace(fvg, state=FVGState.MITIGATED)

    return fvg


def detect_fvg_inversion(candles: list[Candle], fvg: FairValueGap) -> FairValueGap:
    """Detect an inversion: after mitigation, a close through the FVG's
    opposite side flips its role."""
    if fvg.state != FVGState.MITIGATED:
        return fvg

    start_index = fvg.third_candle_index + 1

    for candle in candles[start_index:]:
        if fvg.direction == FVGDirection.BULLISH and candle.close < fvg.lower_price:
            return replace(fvg, state=FVGState.INVERTED)
        if fvg.direction == FVGDirection.BEARISH and candle.close > fvg.upper_price:
            return replace(fvg, state=FVGState.INVERTED)

    return fvg
