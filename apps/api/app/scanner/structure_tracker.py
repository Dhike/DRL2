"""Causally-scoped incremental structure tracking.

StructureTracker accumulates candles one at a time and, on every new
candle, recomputes structure using ONLY the candles seen so far --
never anything from the future. This is what causal ordering requires
for live scanning: a setup's structure must never be influenced by
candles that haven't happened yet from its point of view.

This wraps the already-proven batch `analyze_structure` rather than
reimplementing its internals incrementally. It fixes the correctness
issue (future candles leaking into past structure) found while
building the Liquidity Sweep fixtures; it is not yet a performance
optimization -- each call still rescans the full history held so far.
A true streaming reimplementation (avoiding the rescan) is deferred to
a later phase.
"""

from dataclasses import dataclass, field

from app.market.models import Candle
from app.scanner.analysis import StructureAnalysis, analyze_structure


@dataclass
class StructureTracker:
    candles: list[Candle] = field(default_factory=list)

    def add_candle(self, candle: Candle) -> StructureAnalysis:
        """Append `candle` and return structure computed on the history
        seen so far, including this candle but nothing after it."""
        self.candles.append(candle)
        return analyze_structure(self.candles)

    def current_analysis(self) -> StructureAnalysis:
        """Structure as of the most recently added candle, without adding one."""
        return analyze_structure(self.candles)
