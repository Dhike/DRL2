"""Drives a SetupStateMachine through Trend Continuation's real lifecycle.

Uses the existing, unmodified detect_strong_break / detect_retest /
detect_confirmation functions directly -- no new acceptance rules, no
invented waiting conditions. States describe what is currently being
waited for, not merely the event that caused entry:

    IDLE                   -- nothing yet
    BREAK_DETECTED         -- break recognized, waiting for retest
    RETEST_WAITING         -- retest recognized, waiting for confirmation
    CONFIRMATION_WAITING   -- momentary: entered and left in the same
                               processing step the instant
                               detect_confirmation finds a match
    VALID_SETUP            -- confirmed

IMPORTANT causal note: detect_strong_break requires market_state to be
UPTREND/DOWNTREND, which itself needs several confirmed swings before
it commits to a trend. This means a break can be structurally real
several candles before the system is willing to recognize it as valid
-- once the trend classification catches up, detect_* functions look
back and find it. So a transition is driven by "the system first
recognized this," using the CURRENT candle index for state_entered_at,
never the detected event's own (possibly older) candle_index. The
original event object is kept in machine.context for its true details.
This can mean multiple stages resolve within the same or adjacent
candles if recognition itself was delayed -- that is causally correct,
not a bug.

Level loss and expiry are checked every step, using StructureTracker as
the causally-safe structure source.
"""

from app.market.models import Candle
from app.scanner.level_loss import LevelLossPolicy, has_level_been_lost
from app.scanner.state_machine import SetupState, SetupStateMachine
from app.scanner.structure_tracker import StructureTracker
from app.scanner.trend_continuation import (
    TrendContinuationBreak,
    TrendContinuationRetest,
    detect_confirmation,
    detect_retest,
    detect_strong_break,
)

DEFAULT_MAX_EXPIRY_BARS = 20


def advance_trend_continuation(
    machine: SetupStateMachine,
    tracker: StructureTracker,
    candle: Candle,
    candle_index: int,
    policy: LevelLossPolicy = LevelLossPolicy.STRICT,
    tolerance: float = 0.0,
    max_expiry_bars: int = DEFAULT_MAX_EXPIRY_BARS,
) -> None:
    """Process one new candle for one Trend Continuation setup.

    `candle_index` must match the candle's position as already reflected
    by `tracker` (the candle should already have been added to it).
    """
    analysis = tracker.current_analysis()
    candles = tracker.candles

    if machine.state in (
        SetupState.VALID_SETUP,
        SetupState.TRIGGERED,
        SetupState.INVALIDATED,
        SetupState.EXPIRED,
    ):
        return

    if machine.state == SetupState.IDLE:
        strong_break = detect_strong_break(
            candles, analysis.market_state, list(analysis.bos_events),
            swings=list(analysis.swings),
        )
        if strong_break is not None:
            machine.transition(
                SetupState.BREAK_DETECTED,
                event=strong_break,
                reason=(
                    f"strong {strong_break.direction} break at "
                    f"{strong_break.break_level} recognized"
                ),
                candle_index=candle_index,
            )
            machine.context = strong_break
        return

    if machine.state == SetupState.BREAK_DETECTED:
        strong_break: TrendContinuationBreak = machine.context

        if has_level_been_lost(
            candle, strong_break.break_level, strong_break.direction, policy, tolerance
        ):
            machine.transition(
                SetupState.INVALIDATED,
                event=candle,
                reason=f"level {strong_break.break_level} lost under {policy.value} policy",
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

        retest = detect_retest(candles, strong_break)
        if retest is not None:
            machine.transition(
                SetupState.RETEST_WAITING,
                event=retest,
                reason=f"retest of {retest.break_level} recognized",
                candle_index=candle_index,
            )
            machine.context = retest
        return

    if machine.state == SetupState.RETEST_WAITING:
        retest: TrendContinuationRetest = machine.context

        if has_level_been_lost(
            candle, retest.break_level, retest.direction, policy, tolerance
        ):
            machine.transition(
                SetupState.INVALIDATED,
                event=candle,
                reason=f"level {retest.break_level} lost under {policy.value} policy",
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

        confirmation = detect_confirmation(candles, retest)
        if confirmation is not None:
            machine.transition(
                SetupState.CONFIRMATION_WAITING,
                event=confirmation,
                reason=f"{confirmation.pattern} confirmation detected",
                candle_index=candle_index,
            )
            machine.transition(
                SetupState.VALID_SETUP,
                event=confirmation,
                reason=f"{confirmation.pattern} confirmation accepted",
                candle_index=candle_index,
            )
            machine.context = confirmation
        return
