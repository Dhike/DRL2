from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.analysis import StructureAnalysis
from app.scanner.models import ScannerRequest, ScannerSignal, ScannerStrategy
from app.scanner.strategies import run_strategies
from app.scanner.structure import ExternalStructure, MarketState, StructureScope

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
TC = ScannerStrategy.TREND_CONTINUATION

# Zigzag verified in the structure tests: peaks at 4, 12, 20; troughs at 8, 16, 24.
UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]


def candles_from(rows):
    """Each row is (open, close, high, low)."""
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=1.0,
        )
        for i, (open_, close, high, low) in enumerate(rows)
    ]


def plain_candles():
    return candles_from([(p, p, p + 1.0, p - 1.0) for p in UP_PRICES])


def setup_candles():
    """Same swings as the zigzag; candle 11 is a strong break, 17 a bullish marubozu."""
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[11] = (112.3, 113.8, 114.0, 112.0)
    rows[17] = (110.6, 112.4, 112.5, 110.5)
    return candles_from(rows)


def request(*strategies):
    return ScannerRequest(
        market="crypto",
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=tuple(strategies) or (TC,),
    )


def test_end_to_end_trend_continuation_signal():
    signals = run_strategies(request(), setup_candles())
    assert signals == (
        ScannerSignal(
            market="crypto",
            symbol="BTC/USDT",
            timeframe="1h",
            strategy=TC,
            direction="bullish",
            entry_price=112.4,
            stop_loss=110.5,
            take_profit=None,
            score=0.0,
            reason=(
                "Trend confirmed, strong BOS completed, BOS level retested, "
                "and bullish_marubozu confirmed continuation."
            ),
            structure_scope=StructureScope.EXTERNAL,
        ),
    )


@pytest.mark.parametrize(
    "scope, expected_count",
    [
        pytest.param(StructureScope.EXTERNAL, 1, id="matching-scope"),
        pytest.param(StructureScope.INTERNAL, 0, id="other-scope"),
    ],
)
def test_scope_filter(scope, expected_count):
    assert len(run_strategies(request(), setup_candles(), scope=scope)) == expected_count


def test_no_signal_without_a_setup():
    assert run_strategies(request(), plain_candles()) == ()


def test_at_least_one_strategy_is_required():
    empty = ScannerRequest(
        market="crypto", symbol="BTC/USDT", timeframe="1h", strategies=()
    )
    with pytest.raises(ValueError, match="At least one scanner strategy"):
        run_strategies(empty, setup_candles())


@pytest.mark.parametrize(
    "strategies, named",
    [
        pytest.param((ScannerStrategy.LIQUIDITY_SWEEP,), "liquidity_sweep", id="single"),
        pytest.param((TC, ScannerStrategy.LIQUIDITY_SWEEP), "liquidity_sweep", id="mixed"),
    ],
)
def test_unavailable_strategies_raise_a_clear_error(strategies, named):
    with pytest.raises(ValueError, match=f"not available yet: {named}"):
        run_strategies(request(*strategies), setup_candles())


def test_a_strategy_requested_twice_runs_once():
    assert len(run_strategies(request(TC, TC), setup_candles())) == 1


def test_forming_candles_are_not_analysed(monkeypatch):
    captured = {}

    def fake_analyze(candles):
        captured["candles"] = list(candles)
        return StructureAnalysis(
            market_state=MarketState.UNDEFINED,
            swings=(),
            bos_events=(),
            external=ExternalStructure(
                direction=MarketState.UNDEFINED,
                protected_high=None,
                protected_low=None,
                external_high=None,
                external_low=None,
            ),
        )

    monkeypatch.setattr("app.scanner.strategies.analyze_structure", fake_analyze)

    closed = candles_from([(100 + i, 101 + i, 102 + i, 99 + i) for i in range(6)])
    forming = Candle(
        timestamp=BASE + timedelta(hours=6),
        open=106.0,
        high=109.0,
        low=105.0,
        close=108.0,
        volume=1.0,
        closed=False,
    )
    result = run_strategies(request(), closed + [forming])
    assert captured["candles"] == closed
    assert result == ()


def bullish_break_and_retest_candles():
    """Same zigzag; candle 17 becomes a bullish marubozu confirming the
    111.0 retest -- Break & Retest needs no strong break candle."""
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[17] = (110.6, 112.4, 112.5, 110.5)
    return candles_from(rows)


def test_end_to_end_break_and_retest_signal():
    signals = run_strategies(
        request(ScannerStrategy.BREAK_AND_RETEST), bullish_break_and_retest_candles()
    )
    assert len(signals) == 1
    signal = signals[0]
    assert signal.strategy == ScannerStrategy.BREAK_AND_RETEST
    assert signal.direction == "bullish"
    assert signal.entry_price == 112.4
    assert signal.stop_loss == 110.5
    assert signal.take_profit is None
    assert signal.structure_scope == StructureScope.EXTERNAL
