from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.structure import (
    BreakOfStructure,
    ExternalStructure,
    MarketState,
    SwingPoint,
    analyze_market_structure,
    classify_structure_scope,
    detect_bos,
    find_external_structure,
)


@dataclass(frozen=True)
class StructureAnalysis:
    """Everything the strategies need, computed once from one candle list."""

    market_state: MarketState
    swings: tuple[SwingPoint, ...]
    bos_events: tuple[BreakOfStructure, ...]
    external: ExternalStructure


def closed_candles(candles: list[Candle]) -> list[Candle]:
    """Keep only finished candles: strategies must not see a forming bar."""
    return [candle for candle in candles if candle.closed]


def analyze_structure(candles: list[Candle]) -> StructureAnalysis:
    """Chain the structure engine: swings, labels, market state, breaks and scope.

    The returned swings are labeled and carry their internal or external scope.
    """
    structure = analyze_market_structure(candles)
    labeled = list(structure.swings)

    bos_events = detect_bos(candles, labeled)
    swings = classify_structure_scope(candles, labeled, bos_events)
    external = find_external_structure(list(swings), bos_events, structure.state)

    return StructureAnalysis(
        market_state=structure.state,
        swings=swings,
        bos_events=tuple(bos_events),
        external=external,
    )
