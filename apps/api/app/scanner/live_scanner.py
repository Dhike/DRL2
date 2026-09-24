"""Live, per-symbol/timeframe orchestration of the scanner strategies.

Ties together everything built so far: one StructureTracker per
(symbol, timeframe) -- shared across all strategies for that pair, so
structure is computed once, not three times -- and one
SetupStateMachine per (symbol, timeframe, strategy) via the existing
StateMachineRegistry, guaranteeing the isolation this whole phase was
built to prove.

Strategies to run are passed explicitly on each call to process_candle,
mirroring how the stateless run_strategies API already works, rather
than being configured once up front.

KNOWN LIMITATION (inherited, not new): Liquidity Sweep's adapter needs
an ExternalStructure, supplied here as
tracker.current_analysis().external -- the same thing run_strategies
already does. The index-0 false-CHoCH bug (Step 94) is fixed, but
analysis.external can still lag behind a live, multi-leg reversal in
ways not yet fully characterized; this is the same documented
limitation as Step 85's note on run_strategies, not a new issue.
"""

from app.market.models import Candle
from app.scanner.break_and_retest_adapter import advance_break_and_retest
from app.scanner.level_loss import LevelLossPolicy
from app.scanner.liquidity_sweep_adapter import advance_liquidity_sweep
from app.scanner.models import ScannerStrategy
from app.scanner.state_machine import Scope, StateMachineRegistry
from app.scanner.structure import StructureScope
from app.scanner.structure_tracker import StructureTracker
from app.scanner.trend_continuation_adapter import advance_trend_continuation

DEFAULT_MAX_EXPIRY_BARS = 20


class LiveScanner:
    def __init__(self) -> None:
        self._trackers: dict[tuple[str, str], StructureTracker] = {}
        self._registry = StateMachineRegistry()
        self._candle_counts: dict[tuple[str, str], int] = {}

    def _tracker_for(self, symbol: str, timeframe: str) -> StructureTracker:
        key = (symbol, timeframe)
        if key not in self._trackers:
            self._trackers[key] = StructureTracker()
            self._candle_counts[key] = 0
        return self._trackers[key]

    def process_candle(
        self,
        symbol: str,
        timeframe: str,
        candle: Candle,
        strategies: list[ScannerStrategy],
        scope: StructureScope | None = None,
        policy: LevelLossPolicy = LevelLossPolicy.STRICT,
        tolerance: float = 0.0,
        max_expiry_bars: int = DEFAULT_MAX_EXPIRY_BARS,
    ) -> None:
        """Advance one new candle for `symbol`/`timeframe` across the
        requested `strategies`. Each strategy has its own isolated
        SetupStateMachine; the structure tracker is shared between them
        since it does not depend on the strategy."""
        tracker = self._tracker_for(symbol, timeframe)
        tracker.add_candle(candle)
        key = (symbol, timeframe)
        self._candle_counts[key] += 1
        candle_index = self._candle_counts[key] - 1

        for strategy in strategies:
            machine = self._registry.get(Scope(symbol, timeframe, strategy))

            if strategy == ScannerStrategy.TREND_CONTINUATION:
                advance_trend_continuation(
                    machine, tracker, candle, candle_index, policy, tolerance,
                    max_expiry_bars,
                )
            elif strategy == ScannerStrategy.BREAK_AND_RETEST:
                advance_break_and_retest(
                    machine, tracker, candle, candle_index, policy, tolerance,
                    max_expiry_bars,
                )
            elif strategy == ScannerStrategy.LIQUIDITY_SWEEP:
                external = tracker.current_analysis().external
                advance_liquidity_sweep(
                    machine, tracker, candle, candle_index, external, scope,
                    policy, tolerance, max_expiry_bars,
                )
            else:
                raise ValueError(f"Unknown strategy: {strategy!r}")

    def state_of(self, symbol: str, timeframe: str, strategy: ScannerStrategy):
        return self._registry.get(Scope(symbol, timeframe, strategy))

    def known_scopes(self) -> list[Scope]:
        return self._registry.scopes()
