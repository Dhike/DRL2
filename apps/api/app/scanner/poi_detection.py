"""Runs all 9 POI detectors together against one candle/structure
snapshot, for feeding into the matching engine."""

from app.market.models import Candle
from app.scanner.balanced_price_range import detect_bprs
from app.scanner.breaker_block import detect_breaker_blocks
from app.scanner.fair_value_gap import detect_fair_value_gaps
from app.scanner.mitigation_block import detect_mitigation_blocks
from app.scanner.order_block import detect_order_blocks
from app.scanner.propulsion_block import detect_propulsion_blocks
from app.scanner.reclaimed_order_block import detect_reclaimed_order_blocks
from app.scanner.rejection_block import detect_rejection_blocks
from app.scanner.structure import BreakOfStructure
from app.scanner.vacuum_block import detect_vacuum_blocks


def detect_all_pois(
    candles: list[Candle], bos_events: tuple[BreakOfStructure, ...]
) -> list[object]:
    """All 9 POI types found in this candle history."""
    fvgs = detect_fair_value_gaps(candles)
    order_blocks = detect_order_blocks(candles, bos_events)

    pois: list[object] = list(fvgs)
    pois.extend(detect_bprs(fvgs))
    pois.extend(order_blocks)
    pois.extend(detect_breaker_blocks(candles, order_blocks))
    pois.extend(detect_mitigation_blocks(candles, order_blocks))
    pois.extend(detect_rejection_blocks(candles))
    pois.extend(detect_reclaimed_order_blocks(candles, order_blocks))
    pois.extend(detect_propulsion_blocks(candles, order_blocks))
    pois.extend(detect_vacuum_blocks(candles))
    return pois
