from collections.abc import Callable

from app.market.models import Candle
from app.scanner.analysis import StructureAnalysis, analyze_structure, closed_candles
from app.scanner.models import ScannerRequest, ScannerSignal, ScannerStrategy
from app.scanner.structure import StructureScope
from app.scanner.break_and_retest import detect_break_and_retest_signal
from app.scanner.liquidity_sweep import detect_liquidity_sweep_signal
from app.scanner.trend_continuation import detect_trend_continuation
from app.scanner.risk import compute_take_profit
from app.scanner.poi_detection import detect_all_pois
from app.scanner.poi_matching import match_poi
from app.scanner.scoring import compute_score

StrategyRunner = Callable[
    [ScannerRequest, list[Candle], StructureAnalysis, StructureScope | None, float | None, list[object]],
    ScannerSignal | None,
]


def _find_candle_index(candles: list[Candle], price: float) -> int | None:
    """Best-effort: the most recent candle whose close matches `price`
    (the confirmation candle). Used only for scoring (POI confluence
    lookup), never for strategy validity -- a miss just means poi_score
    falls back to 0, not an error."""
    for index in range(len(candles) - 1, -1, -1):
        if candles[index].close == price:
            return index
    return None


def _finalize_signal(
    *,
    request: ScannerRequest,
    strategy: ScannerStrategy,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float | None,
    reason: str,
    structure_scope: StructureScope,
    confirmation_pattern: str,
    candles: list[Candle],
    all_pois: list[object],
    risk_reward: float | None,
) -> ScannerSignal:
    final_take_profit = take_profit
    if final_take_profit is None and risk_reward is not None:
        final_take_profit = compute_take_profit(
            direction, entry_price, stop_loss, risk_reward
        )

    confirmation_index = _find_candle_index(candles, entry_price)
    poi_matches = []
    if confirmation_index is not None:
        for poi in all_pois:
            result = match_poi(poi, candles, confirmation_index, "CONFIRMATION")
            if result is not None:
                poi_matches.append(result)

    score = compute_score(
        structure_scope,
        poi_matches,
        direction,
        entry_price,
        stop_loss,
        final_take_profit,
        confirmation_pattern,
    )

    return ScannerSignal(
        market=request.market,
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy=strategy,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=final_take_profit,
        score=score,
        reason=reason,
        structure_scope=structure_scope,
    )


def run_trend_continuation(
    request: ScannerRequest,
    candles: list[Candle],
    analysis: StructureAnalysis,
    scope: StructureScope | None,
    risk_reward: float | None,
    all_pois: list[object],
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

    return _finalize_signal(
        request=request,
        strategy=ScannerStrategy.TREND_CONTINUATION,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        reason=signal.reason,
        structure_scope=signal.structure_scope,
        confirmation_pattern=signal.confirmation_pattern,
        candles=candles,
        all_pois=all_pois,
        risk_reward=risk_reward,
    )


def run_break_and_retest(
    request: ScannerRequest,
    candles: list[Candle],
    analysis: StructureAnalysis,
    scope: StructureScope | None,
    risk_reward: float | None,
    all_pois: list[object],
) -> ScannerSignal | None:
    result = detect_break_and_retest_signal(
        candles, list(analysis.swings), list(analysis.bos_events)
    )

    if result.signal is None:
        return None

    if scope is not None and result.signal.structure_scope is not scope:
        return None

    signal = result.signal

    return _finalize_signal(
        request=request,
        strategy=ScannerStrategy.BREAK_AND_RETEST,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        reason=signal.reason,
        structure_scope=signal.structure_scope,
        confirmation_pattern=signal.confirmation_pattern,
        candles=candles,
        all_pois=all_pois,
        risk_reward=risk_reward,
    )


def run_liquidity_sweep(
    request: ScannerRequest,
    candles: list[Candle],
    analysis: StructureAnalysis,
    scope: StructureScope | None,
    risk_reward: float | None,
    all_pois: list[object],
) -> ScannerSignal | None:
    """
    KNOWN LIMITATION: uses the fully-recomputed `analysis.external`, which
    may already reflect structure AFTER the reversal this strategy looks
    for, causing false negatives on setups where a newer swing has
    superseded the original protected level. The correct fix is an
    incrementally-tracked external structure per symbol.
    """
    signal = detect_liquidity_sweep_signal(
        candles, list(analysis.swings), analysis.external, scope=scope
    )

    if signal is None:
        return None

    return _finalize_signal(
        request=request,
        strategy=ScannerStrategy.LIQUIDITY_SWEEP,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        reason=signal.reason,
        structure_scope=signal.structure_scope,
        confirmation_pattern=signal.confirmation_pattern,
        candles=candles,
        all_pois=all_pois,
        risk_reward=risk_reward,
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
    for any signal the engine itself left with take_profit=None. Every
    returned signal's `score` is computed from structure scope, POI
    confluence, risk/reward, and confirmation pattern strength -- scoring
    never affects whether a signal is produced, only its rank.
    """
    if not request.strategies:
        raise ValueError("At least one scanner strategy must be selected.")

    unavailable = [s for s in request.strategies if s not in _RUNNERS]
    if unavailable:
        names = ", ".join(s.value for s in unavailable)
        raise ValueError(f"Scanner strategy not available yet: {names}.")

    closed = closed_candles(candles)
    analysis = analyze_structure(closed)
    all_pois = detect_all_pois(closed, tuple(analysis.bos_events))

    signals: list[ScannerSignal] = []
    for strategy in dict.fromkeys(request.strategies):
        signal = _RUNNERS[strategy](request, closed, analysis, scope, risk_reward, all_pois)
        if signal is not None:
            signals.append(signal)

    return tuple(signals)
