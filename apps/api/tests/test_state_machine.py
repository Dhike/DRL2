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
