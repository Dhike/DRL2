import dataclasses
from collections.abc import Callable

from app.market.models import Candle
from app.scanner.analysis import StructureAnalysis, analyze_structure, closed_candles
from app.scanner.models import ScannerRequest, ScannerSignal, ScannerStrategy
from app.scanner.structure import StructureScope
from app.scanner.break_and_retest import detect_break_and_retest_signal
from app.scanner.liquidity_sweep import detect_liquidity_sweep_signal
from app.scanner.trend_continuation import detect_trend_continuation
from app.scanner.risk import compute_take_profit

# Scores are not defined yet; every signal carries this placeholder.
UNSCORED = 0.0

StrategyRunner = Callable[
    [ScannerRequest, list[Candle], StructureAnalysis, StructureScope | None],
    ScannerSignal | None,
]


def _with_take_profit(
    signal: ScannerSignal, risk_reward: float | None
) -> ScannerSignal:
    """If the engine did not set a take_profit and a risk_reward ratio
    was given, fill one in at a fixed R:R from the entry and stop.
    Leaves an engine-provided take_profit untouched (none currently
    set one, but this stays correct if that ever changes)."""
    if signal.take_profit is not None or risk_reward is None:
        return signal

    take_profit = compute_take_profit(
        signal.direction, signal.entry_price, signal.stop_loss, risk_reward
    )
    return dataclasses.replace(signal, take_profit=take_profit)


def run_trend_continuation(
    request: ScannerRequest,
    candles: list[Candle],
    analysis: StructureAnalysis,
    scope: StructureScope | None = None,
) -> ScannerSignal | None:
    signal = detect_trend_continuation(
        candles,
        analysis.market_state,
        list(analysis.bos_events),
        swings=list(analysis.swings),
        scope=scope,
    )

    if signal is None:
        return None

    return ScannerSignal(
        market=request.market,
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy=ScannerStrategy.TREND_CONTINUATION,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        score=UNSCORED,
        reason=signal.reason,
        structure_scope=signal.structure_scope,
    )


def run_break_and_retest(
    request: ScannerRequest,
    candles: list[Candle],
    analysis: StructureAnalysis,
    scope: StructureScope | None = None,
) -> ScannerSignal | None:
    result = detect_break_and_retest_signal(
        candles, list(analysis.swings), list(analysis.bos_events)
    )

    if result.signal is None:
        return None

    if scope is not None and result.signal.structure_scope is not scope:
        return None

    signal = result.signal

    return ScannerSignal(
        market=request.market,
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy=ScannerStrategy.BREAK_AND_RETEST,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        score=UNSCORED,
        reason=signal.reason,
        structure_scope=signal.structure_scope,
    )


def run_liquidity_sweep(
    request: ScannerRequest,
    candles: list[Candle],
    analysis: StructureAnalysis,
    scope: StructureScope | None = None,
) -> ScannerSignal | None:
    """
    KNOWN LIMITATION: uses the fully-recomputed `analysis.external`, which
    may already reflect structure AFTER the reversal this strategy looks
    for, causing false negatives on setups where a newer swing has
    superseded the original protected level. The correct fix is an
    incrementally-tracked external structure per symbol, planned for the
    state-machine phase.
    """
    signal = detect_liquidity_sweep_signal(
        candles, list(analysis.swings), analysis.external, scope=scope
    )

    if signal is None:
        return None

    return ScannerSignal(
        market=request.market,
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy=ScannerStrategy.LIQUIDITY_SWEEP,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        score=UNSCORED,
        reason=signal.reason,
        structure_scope=signal.structure_scope,
    )


_RUNNERS: dict[ScannerStrategy, StrategyRunner] = {
    ScannerStrategy.TREND_CONTINUATION: run_trend_continuation,
    ScannerStrategy.BREAK_AND_RETEST: run_break_and_retest,
    ScannerStrategy.LIQUIDITY_SWEEP: run_liquidity_sweep,
}


def run_strategies(
    request: ScannerRequest,
    candles: list[Candle],
    scope: StructureScope | None = None,
    risk_reward: float | None = None,
) -> tuple[ScannerSignal, ...]:
    """Run the requested strategies on one symbol's candles.

    Only closed candles are used and the structure is analysed once for all
    strategies. `scope` optionally restricts setups to internal or external
    structure. `risk_reward`, if given, fills in a fixed-ratio take_profit
    for any signal the engine itself left with take_profit=None (every
    engine currently always does); pass None (the default) to leave
    take_profit as the engines produce it.
    """
    if not request.strategies:
        raise ValueError("At least one scanner strategy must be selected.")

    unavailable = [s for s in request.strategies if s not in _RUNNERS]
    if unavailable:
        names = ", ".join(s.value for s in unavailable)
        raise ValueError(f"Scanner strategy not available yet: {names}.")

    closed = closed_candles(candles)
    analysis = analyze_structure(closed)

    signals: list[ScannerSignal] = []
    for strategy in dict.fromkeys(request.strategies):
        signal = _RUNNERS[strategy](request, closed, analysis, scope)
        if signal is not None:
            signals.append(_with_take_profit(signal, risk_reward))

    return tuple(signals)
