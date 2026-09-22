from collections.abc import Callable

from app.market.models import Candle
from app.scanner.analysis import StructureAnalysis, analyze_structure, closed_candles
from app.scanner.models import ScannerRequest, ScannerSignal, ScannerStrategy
from app.scanner.structure import StructureScope
from app.scanner.break_and_retest import detect_break_and_retest_signal
from app.scanner.trend_continuation import detect_trend_continuation

# Scores are not defined yet; every signal carries this placeholder.
UNSCORED = 0.0

StrategyRunner = Callable[
    [ScannerRequest, list[Candle], StructureAnalysis, StructureScope | None],
    ScannerSignal | None,
]


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


_RUNNERS: dict[ScannerStrategy, StrategyRunner] = {
    ScannerStrategy.TREND_CONTINUATION: run_trend_continuation,
    ScannerStrategy.BREAK_AND_RETEST: run_break_and_retest,
}


def run_strategies(
    request: ScannerRequest,
    candles: list[Candle],
    scope: StructureScope | None = None,
) -> tuple[ScannerSignal, ...]:
    """Run the requested strategies on one symbol's candles.

    Only closed candles are used and the structure is analysed once for all
    strategies. `scope` optionally restricts setups to internal or external
    structure.
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
            signals.append(signal)

    return tuple(signals)
