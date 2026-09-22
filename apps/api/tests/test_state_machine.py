import pytest

from app.scanner.models import ScannerStrategy
from app.scanner.state_machine import (
    Scope,
    SetupState,
    StateMachineRegistry,
    TransitionRecord,
)

TC = ScannerStrategy.TREND_CONTINUATION
BR = ScannerStrategy.BREAK_AND_RETEST

EURUSD = Scope("EURUSD", "1h", TC)
GBPUSD = Scope("GBPUSD", "1h", TC)
USDJPY = Scope("USDJPY", "4h", BR)


def test_new_scope_starts_idle():
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    assert machine.state is SetupState.IDLE
    assert machine.history == []


def test_get_returns_the_same_instance_for_the_same_scope():
    registry = StateMachineRegistry()
    first = registry.get(EURUSD)
    first.transition(SetupState.BREAK_DETECTED, event="break", reason="test")
    second = registry.get(EURUSD)
    assert second is first
    assert second.state is SetupState.BREAK_DETECTED


def test_different_scopes_get_independent_instances():
    registry = StateMachineRegistry()
    eur = registry.get(EURUSD)
    gbp = registry.get(GBPUSD)
    assert eur is not gbp
    assert eur.scope != gbp.scope


def test_transition_records_a_full_trace():
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.transition(SetupState.BREAK_DETECTED, event="a break", reason="strong bos")
    assert machine.history == [
        TransitionRecord(
            previous_state=SetupState.IDLE,
            event="a break",
            reason="strong bos",
            new_state=SetupState.BREAK_DETECTED,
        )
    ]


def _scripted_events():
    """Each entry: (scope, new_state, event, reason)."""
    return {
        EURUSD: [
            (SetupState.BREAK_DETECTED, "eur break", "strong bos"),
            (SetupState.RETEST_WAITING, "eur wait", "waiting for retest"),
            (SetupState.RETEST_WAITING, "eur retest touch", "level retested"),
            (SetupState.CONFIRMATION_WAITING, "eur confirm wait", "retest respected"),
            (SetupState.VALID_SETUP, "eur engulfing", "bullish engulfing"),
        ],
        GBPUSD: [
            (SetupState.BREAK_DETECTED, "gbp break", "strong bos"),
            (SetupState.INVALIDATED, "gbp level lost", "strict level loss"),
        ],
        USDJPY: [
            (SetupState.BREAK_DETECTED, "jpy break", "independent break"),
            (SetupState.RETEST_WAITING, "jpy wait", "waiting for retest"),
            (SetupState.EXPIRED, "jpy timeout", "20 candle expiry"),
        ],
    }


def _run_sequential(scripts):
    registry = StateMachineRegistry()
    for scope, steps in scripts.items():
        machine = registry.get(scope)
        for new_state, event, reason in steps:
            machine.transition(new_state, event, reason)
    return registry


def _run_interleaved(scripts):
    """Round-robin the scopes' steps together instead of one scope at a time."""
    registry = StateMachineRegistry()
    max_len = max(len(steps) for steps in scripts.values())
    for i in range(max_len):
        for scope, steps in scripts.items():
            if i < len(steps):
                new_state, event, reason = steps[i]
                registry.get(scope).transition(new_state, event, reason)
    return registry


def test_isolation_sequential_vs_interleaved_processing():
    """
    One scope's events must never mutate another's state. Running all of
    each scope's events back-to-back must produce the exact same final
    state and transition history as interleaving every scope's events
    together, for every scope independently.
    """
    scripts = _scripted_events()

    sequential = _run_sequential(scripts)
    interleaved = _run_interleaved(scripts)

    for scope in scripts:
        seq_machine = sequential.get(scope)
        int_machine = interleaved.get(scope)
        assert seq_machine.state == int_machine.state
        assert seq_machine.history == int_machine.history


def test_isolation_reversed_order_gives_the_same_per_scope_result():
    """Processing scopes in reverse order changes nothing per-scope either."""
    scripts = _scripted_events()

    forward = _run_sequential(scripts)
    reversed_scripts = dict(reversed(list(scripts.items())))
    backward = _run_sequential(reversed_scripts)

    for scope in scripts:
        assert forward.get(scope).state == backward.get(scope).state
        assert forward.get(scope).history == backward.get(scope).history


def test_a_new_scope_appearing_mid_stream_does_not_disturb_existing_ones():
    registry = StateMachineRegistry()
    eur = registry.get(EURUSD)
    eur.transition(SetupState.BREAK_DETECTED, event="eur break", reason="bos")

    # A brand new scope shows up and gets its own independent machine.
    gbp = registry.get(GBPUSD)
    assert gbp.state is SetupState.IDLE
    gbp.transition(SetupState.INVALIDATED, event="gbp noise", reason="strict loss")

    assert eur.state is SetupState.BREAK_DETECTED
    assert len(eur.history) == 1
    assert registry.scopes() == [EURUSD, GBPUSD]


# --- Level loss and expiry ---

from datetime import datetime, timezone

from app.scanner.level_loss import LevelLossPolicy

STRICT = LevelLossPolicy.STRICT
TOLERANT = LevelLossPolicy.TOLERANT
BASE_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_candle(close):
    from app.market.models import Candle

    return Candle(
        timestamp=BASE_TS,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1.0,
    )


@pytest.mark.parametrize(
    "state",
    [
        SetupState.BREAK_DETECTED,
        SetupState.RETEST_WAITING,
        SetupState.CONFIRMATION_WAITING,
        SetupState.VALID_SETUP,
    ],
)
def test_check_level_loss_invalidates_an_at_risk_state(state):
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.state = state

    invalidated = machine.check_level_loss(
        make_candle(99.0), level=100.0, direction="bullish", policy=STRICT
    )

    assert invalidated is True
    assert machine.state is SetupState.INVALIDATED
    assert machine.history[-1].reason == "level 100.0 lost under strict policy"
    assert machine.history[-1].previous_state == state


@pytest.mark.parametrize(
    "state", [SetupState.IDLE, SetupState.TRIGGERED, SetupState.EXPIRED]
)
def test_check_level_loss_is_a_no_op_outside_at_risk_states(state):
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.state = state

    invalidated = machine.check_level_loss(
        make_candle(1.0), level=100.0, direction="bullish", policy=STRICT
    )

    assert invalidated is False
    assert machine.state is state
    assert machine.history == []


def test_check_level_loss_does_nothing_when_the_level_holds():
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.state = SetupState.RETEST_WAITING

    invalidated = machine.check_level_loss(
        make_candle(105.0), level=100.0, direction="bullish", policy=STRICT
    )

    assert invalidated is False
    assert machine.state is SetupState.RETEST_WAITING
    assert machine.history == []


def test_check_level_loss_respects_tolerance():
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.state = SetupState.RETEST_WAITING

    still_within_tolerance = machine.check_level_loss(
        make_candle(99.0),
        level=100.0,
        direction="bullish",
        policy=TOLERANT,
        tolerance=2.0,
    )
    assert still_within_tolerance is False
    assert machine.state is SetupState.RETEST_WAITING

    beyond_tolerance = machine.check_level_loss(
        make_candle(97.0),
        level=100.0,
        direction="bullish",
        policy=TOLERANT,
        tolerance=2.0,
    )
    assert beyond_tolerance is True
    assert machine.state is SetupState.INVALIDATED


@pytest.mark.parametrize(
    "state",
    [
        SetupState.BREAK_DETECTED,
        SetupState.RETEST_WAITING,
        SetupState.CONFIRMATION_WAITING,
    ],
)
def test_check_expiry_expires_a_stalled_waiting_state(state):
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.transition(state, event="entered", reason="test", candle_index=10)

    not_yet = machine.check_expiry(candle_index=29, max_bars=20)
    assert not_yet is False
    assert machine.state is state

    expired = machine.check_expiry(candle_index=30, max_bars=20)
    assert expired is True
    assert machine.state is SetupState.EXPIRED
    assert machine.history[-1].reason == "expired after 20 candles without progress"


def test_check_expiry_does_not_apply_to_valid_setup():
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.transition(
        SetupState.VALID_SETUP, event="confirmed", reason="test", candle_index=0
    )

    expired = machine.check_expiry(candle_index=100, max_bars=20)

    assert expired is False
    assert machine.state is SetupState.VALID_SETUP


def test_check_expiry_does_nothing_without_a_known_entry_index():
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.state = SetupState.RETEST_WAITING  # bypasses transition(), no index set

    expired = machine.check_expiry(candle_index=1000, max_bars=20)

    assert expired is False
    assert machine.state is SetupState.RETEST_WAITING


def test_transition_without_candle_index_leaves_state_entered_at_unchanged():
    registry = StateMachineRegistry()
    machine = registry.get(EURUSD)
    machine.transition(SetupState.BREAK_DETECTED, event="a", reason="b", candle_index=5)
    machine.transition(SetupState.RETEST_WAITING, event="c", reason="d")

    assert machine.state_entered_at == 5
    assert machine.check_expiry(candle_index=24, max_bars=20) is False
    assert machine.check_expiry(candle_index=25, max_bars=20) is True


def test_level_loss_and_expiry_remain_isolated_across_scopes():
    registry = StateMachineRegistry()
    eur = registry.get(EURUSD)
    gbp = registry.get(GBPUSD)

    eur.transition(SetupState.RETEST_WAITING, event="a", reason="b", candle_index=0)
    gbp.transition(SetupState.RETEST_WAITING, event="a", reason="b", candle_index=0)

    eur.check_level_loss(
        make_candle(1.0), level=100.0, direction="bullish", policy=STRICT
    )

    assert eur.state is SetupState.INVALIDATED
    assert gbp.state is SetupState.RETEST_WAITING
    assert len(gbp.history) == 1  # only its own RETEST_WAITING entry, no invalidation
