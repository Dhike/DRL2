"""Level-loss policy: has a setup's protected level been violated?

Independent of the state machine so it can be tested in isolation and
swapped per symbol/strategy later. Checks the candle's CLOSE, matching
the close-based convention already used by every break, retest and
change-of-character check elsewhere in this engine -- a wick crossing
the level without the candle closing past it is not treated as a loss.
"""

from enum import StrEnum

from app.market.models import Candle


class LevelLossPolicy(StrEnum):
    STRICT = "strict"
    TOLERANT = "tolerant"


def has_level_been_lost(
    candle: Candle,
    level: float,
    direction: str,
    policy: LevelLossPolicy,
    tolerance: float = 0.0,
) -> bool:
    """
    True if `candle` shows the setup's level has been lost.

    `direction` is the setup's own direction ("bullish" or "bearish"),
    matching the convention used across the strategy engines. STRICT
    treats any close beyond the level as a loss (tolerance is ignored).
    TOLERANT only counts a loss once the close is beyond `level` by
    more than `tolerance`.
    """
    effective_tolerance = tolerance if policy == LevelLossPolicy.TOLERANT else 0.0

    if direction == "bullish":
        return candle.close < level - effective_tolerance

    if direction == "bearish":
        return candle.close > level + effective_tolerance

    raise ValueError(f"Unknown direction: {direction!r}")
