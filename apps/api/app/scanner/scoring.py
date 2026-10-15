"""Scoring: a 0-100 ranking score for a confirmed ScannerSignal.

Per user's explicit design: a weighted sum of four factors. Scoring
NEVER changes whether a setup is valid -- the existing strategy rules
already decided that. A setup with a weak score is still a real,
valid setup; it simply ranks lower.

    structure scope    30%  (external > internal)
    POI confluence     30%  (overlapping > near > none)
    risk/reward        25%  (capped at a 1:5 ceiling)
    confirmation       15%  (pattern strength)

Confirmation pattern weights: user specified 5 explicitly (engulfing,
marubozu, hammer, shooting star, pin bar); the remaining 13 patterns
in the shared confirmation library are this module's own extrapolation
of the same scale, not independently specified.
"""

from app.scanner.poi_matching import POIMatch
from app.scanner.structure import StructureScope

WEIGHTS = {
    "structure": 0.30,
    "poi": 0.30,
    "risk_reward": 0.25,
    "confirmation": 0.15,
}

MAX_RISK_REWARD = 5.0

STRUCTURE_SCORES: dict[StructureScope, float] = {
    StructureScope.EXTERNAL: 100.0,
    StructureScope.INTERNAL: 50.0,
    StructureScope.UNDEFINED: 0.0,
}

# User-specified: engulfing, marubozu, hammer/shooting_star, pin_bar.
# Everything else below is this module's own extrapolation of the same
# scale, not independently specified by the user.
CONFIRMATION_PATTERN_SCORES: dict[str, float] = {
    "bullish_engulfing": 100.0,
    "bearish_engulfing": 100.0,
    "bullish_marubozu": 90.0,
    "bearish_marubozu": 90.0,
    "morning_star": 85.0,
    "evening_star": 85.0,
    "three_white_soldiers": 80.0,
    "three_black_crows": 80.0,
    "hammer": 75.0,
    "shooting_star": 75.0,
    "rising_three_methods": 70.0,
    "falling_three_methods": 70.0,
    "bullish_pin_bar": 65.0,
    "bearish_pin_bar": 65.0,
    "bullish_outside_bar": 60.0,
    "bearish_outside_bar": 60.0,
    "bullish_inside_bar_breakout": 55.0,
    "bearish_inside_bar_breakout": 55.0,
}
DEFAULT_CONFIRMATION_SCORE = 50.0


def structure_score(scope: StructureScope) -> float:
    return STRUCTURE_SCORES.get(scope, 0.0)


def poi_score(matches: list[POIMatch]) -> float:
    if any(m.overlap for m in matches):
        return 100.0
    if any(m.near for m in matches):
        return 70.0
    return 0.0


def risk_reward_score(
    direction: str, entry_price: float, stop_loss: float, take_profit: float | None
) -> float:
    if take_profit is None:
        return 0.0

    if direction == "bullish":
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
    elif direction == "bearish":
        risk = stop_loss - entry_price
        reward = entry_price - take_profit
    else:
        return 0.0

    if risk <= 0 or reward <= 0:
        return 0.0

    rr = reward / risk
    return min(rr / MAX_RISK_REWARD, 1.0) * 100.0


def confirmation_score(pattern: str) -> float:
    return CONFIRMATION_PATTERN_SCORES.get(pattern, DEFAULT_CONFIRMATION_SCORE)


def compute_score(
    scope: StructureScope,
    poi_matches: list[POIMatch],
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float | None,
    confirmation_pattern: str,
) -> float:
    total = (
        structure_score(scope) * WEIGHTS["structure"]
        + poi_score(poi_matches) * WEIGHTS["poi"]
        + risk_reward_score(direction, entry_price, stop_loss, take_profit)
        * WEIGHTS["risk_reward"]
        + confirmation_score(confirmation_pattern) * WEIGHTS["confirmation"]
    )
    return round(total, 2)
