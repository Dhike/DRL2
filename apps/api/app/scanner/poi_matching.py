"""POI matching engine: compares any of the 9 POI types against a
setup's retest or confirmation candle, per the locked matching
contract (overlap / near / interaction / status eligibility).

Order-Block-family POIs (OrderBlock, BreakerBlock, MitigationBlock,
ReclaimedOrderBlock, PropulsionBlock) get a computed BODY zone and
WICK-EXTREME invalidation boundary here, per the locked OB geometry
rule -- the 5 already-shipped detector modules themselves are left
UNCHANGED (still store the full wick range as high_price/low_price);
this is an additional computed view, not a stored field change.

DEEP_INTERACTION and REACTION (from the design doc) are deliberately
NOT implemented yet -- both need their own separate rules the doc
left undefined; scope-trimmed here to ship the core contract first.
"""

from dataclasses import dataclass
from typing import Literal

from app.market.models import Candle
from app.scanner.balanced_price_range import BalancedPriceRange
from app.scanner.breaker_block import BreakerBlock
from app.scanner.fair_value_gap import FairValueGap, FVGDirection, FVGState
from app.scanner.mitigation_block import MitigationBlock
from app.scanner.order_block import OrderBlock
from app.scanner.propulsion_block import PropulsionBlock
from app.scanner.reclaimed_order_block import ReclaimedOrderBlock
from app.scanner.rejection_block import RejectionBlock
from app.scanner.vacuum_block import VacuumBlock

InteractionLevel = Literal["NONE", "WICK_TOUCH", "CLOSED_INSIDE", "CLOSED_THROUGH"]
MatchContext = Literal["RETEST", "CONFIRMATION"]

_OB_FAMILY = (OrderBlock, BreakerBlock, MitigationBlock, ReclaimedOrderBlock, PropulsionBlock)
_ZONE_LOWER_UPPER = (FairValueGap, BalancedPriceRange)


def poi_type_label(poi: object) -> str:
    return type(poi).__name__


def poi_status(poi: object) -> FVGState:
    """RejectionBlock has no `state` field -- treated as always ACTIVE."""
    return getattr(poi, "state", FVGState.ACTIVE)


def poi_direction(poi: object) -> FVGDirection | None:
    """BalancedPriceRange has no single direction of its own."""
    if isinstance(poi, BalancedPriceRange):
        return None
    return getattr(poi, "direction", None)


def poi_zone(poi: object) -> tuple[float, float]:
    """Return (zone_low, zone_high) for any of the 9 POI types."""
    if isinstance(poi, _ZONE_LOWER_UPPER):
        return poi.lower_price, poi.upper_price
    if hasattr(poi, "low_price") and hasattr(poi, "high_price"):
        return poi.low_price, poi.high_price
    raise TypeError(f"Unrecognized POI type: {type(poi)!r}")


def ob_family_boundaries(poi: object) -> tuple[float, float, float] | None:
    """For Order-Block-family POIs: (body_low, body_high,
    invalidation_boundary) per the locked geometry rule. None for any
    other POI type."""
    if not isinstance(poi, _OB_FAMILY):
        return None
    body_low = min(poi.open_price, poi.close_price)
    body_high = max(poi.open_price, poi.close_price)
    invalidation_boundary = (
        poi.low_price if poi.direction == FVGDirection.BULLISH else poi.high_price
    )
    return body_low, body_high, invalidation_boundary


def compute_overlap(a_low: float, a_high: float, b_low: float, b_high: float) -> bool:
    return max(a_low, b_low) <= min(a_high, b_high)


def compute_distance(zone_low: float, zone_high: float, ref_low: float, ref_high: float) -> float:
    """0 if the ranges overlap, else the gap between their nearest
    boundaries."""
    if compute_overlap(zone_low, zone_high, ref_low, ref_high):
        return 0.0
    if ref_high < zone_low:
        return zone_low - ref_high
    return ref_low - zone_high


def average_true_range(candles: list[Candle], period: int = 14) -> float | None:
    """Simple (non-Wilder) average true range over the last `period`
    candles. None if there isn't enough history."""
    if len(candles) < period + 1:
        return None
    true_ranges = []
    for i in range(len(candles) - period, len(candles)):
        prev_close = candles[i - 1].close
        candle = candles[i]
        true_ranges.append(
            max(candle.high - candle.low, abs(candle.high - prev_close), abs(candle.low - prev_close))
        )
    return sum(true_ranges) / period


def classify_interaction(zone_low: float, zone_high: float, candle: Candle) -> InteractionLevel:
    """
    NONE: candle's wick range never reaches the zone.
    WICK_TOUCH: wick reaches the zone, but the candle's BODY does not.
    CLOSED_INSIDE: the body reaches the zone and the close lands within it.
    CLOSED_THROUGH: the body reaches the zone but the close lands outside it
    (the candle's body passed through the zone).
    """
    touched = candle.low <= zone_high and candle.high >= zone_low
    if not touched:
        return "NONE"

    body_low = min(candle.open, candle.close)
    body_high = max(candle.open, candle.close)
    body_touches = body_low <= zone_high and body_high >= zone_low
    if not body_touches:
        return "WICK_TOUCH"

    if zone_low <= candle.close <= zone_high:
        return "CLOSED_INSIDE"
    return "CLOSED_THROUGH"


@dataclass(frozen=True)
class POIMatch:
    poi: object
    poi_type: str
    direction: FVGDirection | None
    status: FVGState
    overlap: bool
    near: bool
    distance_atr: float | None
    interaction: InteractionLevel
    match_context: MatchContext


def match_poi(
    poi: object,
    candles: list[Candle],
    reference_index: int,
    match_context: MatchContext,
    near_threshold: float = 0.25,
) -> POIMatch | None:
    """
    Match one POI against the candle at `reference_index` (the retest
    or confirmation candle -- callers must pass the correct index for
    RETEST_MATCH vs CONFIRMATION_MATCH separately, never a merged range).

    Returns None if the POI's status makes it ineligible for ordinary
    confluence (anything other than ACTIVE or MITIGATED -- INVERTED,
    INVALIDATED, EXPIRED are excluded per the locked contract).
    """
    status = poi_status(poi)
    if status not in (FVGState.ACTIVE, FVGState.MITIGATED):
        return None

    zone_low, zone_high = poi_zone(poi)
    candle = candles[reference_index]

    overlap = compute_overlap(zone_low, zone_high, candle.low, candle.high)
    distance = compute_distance(zone_low, zone_high, candle.low, candle.high)

    atr = average_true_range(candles[:reference_index])  # excludes the reference candle itself
    if atr is not None and atr > 0:
        distance_atr = distance / atr
        near = distance_atr <= near_threshold
    else:
        distance_atr = None
        near = overlap  # can't normalize without enough history

    return POIMatch(
        poi=poi,
        poi_type=poi_type_label(poi),
        direction=poi_direction(poi),
        status=status,
        overlap=overlap,
        near=near,
        distance_atr=distance_atr,
        interaction=classify_interaction(zone_low, zone_high, candle),
        match_context=match_context,
    )
