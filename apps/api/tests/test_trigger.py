from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.break_and_retest import BreakAndRetestSignal
from app.scanner.liquidity_sweep import LiquiditySweepSignal
from app.scanner.models import ScannerStrategy
from app.scanner.state_machine import Scope, SetupState, SetupStateMachine
from app.scanner.structure import BreakOfStructure, StructureScope
from app.scanner.trend_continuation import (
    TrendContinuationConfirmation,
    TrendContinuationRetest,
)
from app.scanner.trigger import check_stop_hit

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXT = StructureScope.EXTERNAL


def make_candle(low=None, high=None, close=None):
    """
    Build a valid candle whose wick reaches whichever of low/high is
    given. open/close are kept sensibly between them -- not a fixed
    default -- since low/high are usually chosen relative to a specific
    stop level far from any fixed price.
    """
    if low is not None and high is not None:
        mid = (low + high) / 2
    elif low is not None:
        high = low + 1.0
        mid = low + 0.5
    elif high is not None:
        low = high - 1.0
        mid = high - 0.5
    else:
        low, high, mid = 99.0, 101.0, 100.0

    close = close if close is not None else mid
    close = min(max(close, low), high)  # keep it inside the wick range

    return Candle(
        timestamp=BASE, open=close, high=high, low=low, close=close, volume=1.0,
    )


def scope(strategy):
    return Scope("BTC/USDT", "1h", strategy)


def test_no_op_outside_valid_setup():
    machine = SetupStateMachine(scope(ScannerStrategy.BREAK_AND_RETEST))
    machine.state = SetupState.RETEST_WAITING
    machine.context = BreakAndRetestSignal(
        direction="bullish", entry_price=112.0, stop_loss=110.0, take_profit=None,
        break_level=111.0, confirmation_pattern="x", reason="x", structure_scope=EXT,
    )
    hit = check_stop_hit(machine, make_candle(low=100.0), 5)
    assert hit is False
    assert machine.state is SetupState.RETEST_WAITING


def test_break_and_retest_bullish_stop_hit():
    machine = SetupStateMachine(scope(ScannerStrategy.BREAK_AND_RETEST))
    machine.state = SetupState.VALID_SETUP
    machine.context = BreakAndRetestSignal(
        direction="bullish", entry_price=112.0, stop_loss=110.0, take_profit=None,
        break_level=111.0, confirmation_pattern="x", reason="x", structure_scope=EXT,
    )
    hit = check_stop_hit(machine, make_candle(low=109.9), 5)
    assert hit is True
    assert machine.state is SetupState.TRIGGERED
    assert machine.history[-1].reason == "stop-loss 110.0 hit"


def test_break_and_retest_bullish_stop_not_hit():
    machine = SetupStateMachine(scope(ScannerStrategy.BREAK_AND_RETEST))
    machine.state = SetupState.VALID_SETUP
    machine.context = BreakAndRetestSignal(
        direction="bullish", entry_price=112.0, stop_loss=110.0, take_profit=None,
        break_level=111.0, confirmation_pattern="x", reason="x", structure_scope=EXT,
    )
    hit = check_stop_hit(machine, make_candle(low=110.1), 5)
    assert hit is False
    assert machine.state is SetupState.VALID_SETUP


def test_liquidity_sweep_bearish_stop_hit():
    machine = SetupStateMachine(scope(ScannerStrategy.LIQUIDITY_SWEEP))
    machine.state = SetupState.VALID_SETUP
    machine.context = LiquiditySweepSignal(
        direction="bearish", entry_price=98.0, stop_loss=100.0, take_profit=None,
        swept_level=99.0, confirmation_pattern="x", reason="x", structure_scope=EXT,
    )
    hit = check_stop_hit(machine, make_candle(high=100.1), 5)
    assert hit is True
    assert machine.state is SetupState.TRIGGERED
    assert machine.history[-1].reason == "stop-loss 100.0 hit"


def test_liquidity_sweep_bearish_stop_not_hit():
    machine = SetupStateMachine(scope(ScannerStrategy.LIQUIDITY_SWEEP))
    machine.state = SetupState.VALID_SETUP
    machine.context = LiquiditySweepSignal(
        direction="bearish", entry_price=98.0, stop_loss=100.0, take_profit=None,
        swept_level=99.0, confirmation_pattern="x", reason="x", structure_scope=EXT,
    )
    hit = check_stop_hit(machine, make_candle(high=99.9), 5)
    assert hit is False
    assert machine.state is SetupState.VALID_SETUP


def _trend_continuation_confirmation(direction="bullish"):
    bos = BreakOfStructure(direction, 111.0, 11, BASE)
    retest_candle = make_candle(low=111.0, high=112.0, close=111.5)
    retest = TrendContinuationRetest(
        direction=direction, break_level=111.0, break_index=11, retest_index=14,
        candle=retest_candle, bos=bos, structure_scope=EXT,
    )
    confirmation_candle = make_candle(low=110.5, high=112.5, close=112.4)
    return TrendContinuationConfirmation(
        direction=direction, confirmation_index=17, pattern="bullish_marubozu",
        candle=confirmation_candle, retest=retest,
    )


def test_trend_continuation_bullish_stop_hit():
    """
    stop_loss = min(retest_candle.low=111.0, confirmation_candle.low=110.5)
    = 110.5, computed from context fields, not a stored stop_loss field.
    """
    machine = SetupStateMachine(scope(ScannerStrategy.TREND_CONTINUATION))
    machine.state = SetupState.VALID_SETUP
    machine.context = _trend_continuation_confirmation()

    hit = check_stop_hit(machine, make_candle(low=110.4), 20)
    assert hit is True
    assert machine.state is SetupState.TRIGGERED
    assert machine.history[-1].reason == "stop-loss 110.5 hit"


def test_trend_continuation_bullish_stop_not_hit():
    machine = SetupStateMachine(scope(ScannerStrategy.TREND_CONTINUATION))
    machine.state = SetupState.VALID_SETUP
    machine.context = _trend_continuation_confirmation()

    hit = check_stop_hit(machine, make_candle(low=110.6), 20)
    assert hit is False
    assert machine.state is SetupState.VALID_SETUP


def test_resolved_states_other_than_valid_setup_are_untouched():
    for state in (
        SetupState.TRIGGERED, SetupState.INVALIDATED, SetupState.EXPIRED, SetupState.IDLE,
    ):
        machine = SetupStateMachine(scope(ScannerStrategy.BREAK_AND_RETEST))
        machine.state = state
        machine.context = BreakAndRetestSignal(
            direction="bullish", entry_price=112.0, stop_loss=110.0, take_profit=None,
            break_level=111.0, confirmation_pattern="x", reason="x", structure_scope=EXT,
        )
        hit = check_stop_hit(machine, make_candle(low=1.0), 5)
        assert hit is False
        assert machine.state is state
