from dataclasses import FrozenInstanceError

import pytest

from app.scanner.models import (
    ScannerRequest,
    ScannerResult,
    ScannerSignal,
    ScannerStatus,
    ScannerStrategy,
)
from app.scanner.structure import StructureScope


def make_signal(**overrides):
    values = dict(
        market="crypto",
        symbol="BTC/USDT",
        timeframe="1h",
        strategy=ScannerStrategy.TREND_CONTINUATION,
        direction="bullish",
        entry_price=104.0,
        stop_loss=100.0,
        take_profit=None,
        score=0.0,
        reason="test",
    )
    values.update(overrides)
    return ScannerSignal(**values)


def make_request():
    return ScannerRequest(
        market="crypto",
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=(ScannerStrategy.BREAK_AND_RETEST,),
    )


def test_strategy_values():
    assert {s.value for s in ScannerStrategy} == {
        "liquidity_sweep",
        "trend_continuation",
        "break_and_retest",
    }


def test_status_values():
    assert {s.value for s in ScannerStatus} == {
        "waiting",
        "scanning",
        "completed",
        "failed",
    }


def test_request_keeps_its_fields():
    request = make_request()
    assert (request.market, request.symbol, request.timeframe) == (
        "crypto",
        "BTC/USDT",
        "1h",
    )
    assert request.strategies == (ScannerStrategy.BREAK_AND_RETEST,)


def test_signal_defaults_to_undefined_scope_and_may_have_no_take_profit():
    signal = make_signal()
    assert signal.structure_scope is StructureScope.UNDEFINED
    assert signal.take_profit is None


def test_signal_carries_the_structure_scope():
    signal = make_signal(structure_scope=StructureScope.EXTERNAL, take_profit=110.0)
    assert signal.structure_scope is StructureScope.EXTERNAL
    assert signal.take_profit == 110.0


def test_result_holds_its_signals_as_a_tuple():
    signals = (make_signal(), make_signal(direction="bearish"))
    result = ScannerResult(status=ScannerStatus.COMPLETED, signals=signals)
    assert result.status is ScannerStatus.COMPLETED
    assert result.signals == signals
    assert isinstance(result.signals, tuple)


@pytest.mark.parametrize(
    "build, field",
    [
        pytest.param(make_request, "symbol", id="request"),
        pytest.param(make_signal, "entry_price", id="signal"),
        pytest.param(
            lambda: ScannerResult(status=ScannerStatus.WAITING, signals=()),
            "status",
            id="result",
        ),
    ],
)
def test_dataclasses_are_frozen(build, field):
    with pytest.raises(FrozenInstanceError):
        setattr(build(), field, 1)
