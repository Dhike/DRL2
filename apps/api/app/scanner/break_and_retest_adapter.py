"""Drives a SetupStateMachine through Break & Retest's real lifecycle.

Unlike Trend Continuation, this engine does not depend on market_state,
so its internal states progress causally without a recognition-lag
issue -- confirmed by dry run. Mapping:

    WAITING_FOR_BREAK                    -> IDLE
    WAITING_FOR_BULLISH/BEARISH_RETEST   -> BREAK_DETECTED
    WAITING_FOR_BULLISH/BEARISH_CONFIRMATION -> RETEST_WAITING
    signal produced (CONFIRMED)          -> CONFIRMATION_WAITING -> VALID_SETUP
                                             (momentary, same as Trend
                                             Continuation: no separate
                                             acceptance step exists)

While waiting for the retest, the engine's own `setup` object is still
None, so the level to check for loss is taken from the same private
_candidate_bos_events selection the engine itself uses -- not a
re-derived approximation.
"""

from app.market.models import Candle
from app.scanner.break_and_retest import (
    BreakAndRetestSetup,
    BreakAndRetestState,
    _candidate_bos_events,
    detect_break_and_retest_signal,
)
from app.scanner.level_loss import LevelLossPolicy, has_level_been_lost
from app.scanner.state_machine import SetupState, SetupStateMachine
from app.scanner.structure_tracker import StructureTracker

DEFAULT_MAX_EXPIRY_BARS = 20

RETEST_WAITING_ENGINE_STATES = (
    BreakAndRetestState.WAITING_FOR_BULLISH_RETEST,
    BreakAndRetestState.WAITING_FOR_BEARISH_RETEST,
)
CONFIRMATION_WAITING_ENGINE_STATES = (
    BreakAndRetestState.WAITING_FOR_BULLISH_CONFIRMATION,
    BreakAndRetestState.WAITING_FOR_BEARISH_CONFIRMATION,
)


def advance_break_and_retest(
    machine: SetupStateMachine,
    tracker: StructureTracker,
    candle: Candle,
    candle_index: int,
    policy: LevelLossPolicy = LevelLossPolicy.STRICT,
    tolerance: float = 0.0,
    max_expiry_bars: int = DEFAULT_MAX_EXPIRY_BARS,
) -> None:
    """Process one new candle for one Break & Retest setup."""
    if machine.state in (
        SetupState.VALID_SETUP,
        SetupState.TRIGGERED,
        SetupState.INVALIDATED,
        SetupState.EXPIRED,
    ):
        return

    analysis = tracker.current_analysis()
    candles = tracker.candles

    if machine.state == SetupState.IDLE:
        result = detect_break_and_retest_signal(
            candles, list(analysis.swings), list(analysis.bos_events)
        )
        if result.state in RETEST_WAITING_ENGINE_STATES:
            candidates = _candidate_bos_events(
                list(analysis.swings), list(analysis.bos_events)
            )
            latest_bos = candidates[-1][0] if candidates else None
            machine.transition(
                SetupState.BREAK_DETECTED,
                event=latest_bos,
                reason=f"break recognized ({result.state.value})",
                candle_index=candle_index,
            )
            machine.context = latest_bos
        return

    if machine.state == SetupState.BREAK_DETECTED:
        latest_bos = machine.context
        if latest_bos is not None and has_level_been_lost(
            candle, latest_bos.broken_level, latest_bos.direction, policy, tolerance
        ):
            machine.transition(
                SetupState.INVALIDATED,
                event=candle,
                reason=f"level {latest_bos.broken_level} lost under {policy.value} policy",
                candle_index=candle_index,
            )
            return

        if candle_index - machine.state_entered_at >= max_expiry_bars:
            machine.transition(
                SetupState.EXPIRED,
                event=None,
                reason=f"expired after {max_expiry_bars} candles without a retest",
                candle_index=candle_index,
            )
            return

        result = detect_break_and_retest_signal(
            candles, list(analysis.swings), list(analysis.bos_events)
        )
        if result.state in CONFIRMATION_WAITING_ENGINE_STATES:
            machine.transition(
                SetupState.RETEST_WAITING,
                event=result.setup,
                reason=f"retest recognized ({result.state.value})",
                candle_index=candle_index,
            )
            machine.context = result.setup
        return

    if machine.state == SetupState.RETEST_WAITING:
        setup: BreakAndRetestSetup = machine.context
        if has_level_been_lost(
            candle, setup.break_level, setup.direction, policy, tolerance
        ):
            machine.transition(
                SetupState.INVALIDATED,
                event=candle,
                reason=f"level {setup.break_level} lost under {policy.value} policy",
                candle_index=candle_index,
            )
            return

        if candle_index - machine.state_entered_at >= max_expiry_bars:
            machine.transition(
                SetupState.EXPIRED,
                event=None,
                reason=f"expired after {max_expiry_bars} candles without confirmation",
                candle_index=candle_index,
            )
            return

        result = detect_break_and_retest_signal(
            candles, list(analysis.swings), list(analysis.bos_events)
        )
        if result.signal is not None:
            machine.transition(
                SetupState.CONFIRMATION_WAITING,
                event=result.signal,
                reason=f"{result.signal.confirmation_pattern} confirmation detected",
                candle_index=candle_index,
            )
            machine.transition(
                SetupState.VALID_SETUP,
                event=result.signal,
                reason=f"{result.signal.confirmation_pattern} confirmation accepted",
                candle_index=candle_index,
            )
            machine.context = result.signal
        return
