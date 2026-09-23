"""Drives a SetupStateMachine through Liquidity Sweep's real lifecycle.

Liquidity Sweep's engine (detect_liquidity_sweep_signal) exposes no
partial-progress states of its own, unlike Break & Retest -- it is a
single all-or-nothing function. Per explicit user choice (Option 2),
this adapter infers staged progress from the engine's own lower-level
building blocks rather than treating this as a single-step IDLE ->
VALID_SETUP jump:

    IDLE           -- nothing yet
    BREAK_DETECTED -- sweep + return + CHoCH recognized,
                       waiting for the structural post-CHoCH BOS
    RETEST_WAITING -- BOS recognized, waiting for candlestick
                       confirmation
    CONFIRMATION_WAITING -> VALID_SETUP -- momentary, same as the
                       other two adapters (no separate acceptance step
                       exists in the engine)

This mapping is this adapter's own interpretation of how Liquidity
Sweep's stages correspond to the shared state vocabulary -- the
vocabulary was defined against Trend Continuation and Break & Retest's
shapes, and Liquidity Sweep's shape (sweep/return/CHoCH/BOS) doesn't
have a natural "break" or "retest" in their sense. BREAK_DETECTED here
means "the reversal is recognized, awaiting structural confirmation";
RETEST_WAITING means "structurally confirmed, awaiting candlestick
confirmation."

Once CHoCH and BOS both already exist, the final signal is obtained by
calling the real detect_liquidity_sweep_signal directly rather than
reconstructing it by hand -- single source of truth, no duplicated
signal-building logic.

KNOWN LIMITATION (documented, not fixed here): `external` must be
supplied by the caller, same as detect_liquidity_sweep_signal itself.
Deriving it automatically and causally per-candle in production is
currently broken -- detect_choch scans the whole candle list from
index 0 every time, so a downtrend's real protected level (set by a
swing that confirms only after several candles) is preceded by an
artificial false CHoCH at candle 0 in almost every real sequence,
since candle 0's own close is very often already beyond that level by
construction. This is the same root issue already logged against
run_liquidity_sweep in strategies.py (Step 85), now confirmed more
severe by direct dry run: the real CHoCH is effectively unreachable
causally until this is fixed (part of the deferred B2 work).
"""

from app.market.models import Candle
from app.scanner.level_loss import LevelLossPolicy, has_level_been_lost
from app.scanner.liquidity_sweep import (
    detect_liquidity_levels,
    detect_liquidity_returns,
    detect_liquidity_sweeps,
    detect_liquidity_sweep_signal,
    detect_post_choch_bos,
)
from app.scanner.state_machine import SetupState, SetupStateMachine
from app.scanner.structure import ExternalStructure, StructureScope, detect_choch
from app.scanner.structure_tracker import StructureTracker

DEFAULT_MAX_EXPIRY_BARS = 20


def _find_matching_return(candles, swings, external, choch, scope):
    expected_side = "buy_side" if choch.direction == "bearish" else "sell_side"
    levels = detect_liquidity_levels(candles, tuple(swings), scope)
    sweeps = detect_liquidity_sweeps(candles, levels)
    returns = detect_liquidity_returns(candles, sweeps)

    matching_return = None
    for candidate in returns:
        if candidate.side != expected_side:
            continue
        if candidate.return_index >= choch.candle_index:
            continue
        matching_return = candidate
    return matching_return


def advance_liquidity_sweep(
    machine: SetupStateMachine,
    tracker: StructureTracker,
    candle: Candle,
    candle_index: int,
    external: ExternalStructure,
    scope: StructureScope | None = None,
    policy: LevelLossPolicy = LevelLossPolicy.STRICT,
    tolerance: float = 0.0,
    max_expiry_bars: int = DEFAULT_MAX_EXPIRY_BARS,
) -> None:
    """Process one new candle for one Liquidity Sweep setup.

    `external` must be supplied by the caller (see the module-level
    limitation note); it is not derived from `tracker`.
    """
    if machine.state in (
        SetupState.VALID_SETUP,
        SetupState.TRIGGERED,
        SetupState.INVALIDATED,
        SetupState.EXPIRED,
    ):
        return

    analysis = tracker.current_analysis()
    candles = tracker.candles
    swings = list(analysis.swings)

    if machine.state == SetupState.IDLE:
        choch = detect_choch(candles, external)
        if choch is None:
            return

        matching_return = _find_matching_return(candles, swings, external, choch, scope)
        if matching_return is None:
            return

        machine.transition(
            SetupState.BREAK_DETECTED,
            event=(choch, matching_return),
            reason=(
                f"{matching_return.side} liquidity sweep at "
                f"{matching_return.liquidity_price} and CHoCH recognized, "
                f"awaiting structural BOS"
            ),
            candle_index=candle_index,
        )
        machine.context = (choch, matching_return)
        return

    if machine.state == SetupState.BREAK_DETECTED:
        stored_choch, matching_return = machine.context

        if has_level_been_lost(
            candle, stored_choch.broken_level, stored_choch.direction, policy, tolerance
        ):
            machine.transition(
                SetupState.INVALIDATED,
                event=candle,
                reason=(
                    f"level {stored_choch.broken_level} lost under "
                    f"{policy.value} policy"
                ),
                candle_index=candle_index,
            )
            return

        if candle_index - machine.state_entered_at >= max_expiry_bars:
            machine.transition(
                SetupState.EXPIRED,
                event=None,
                reason=f"expired after {max_expiry_bars} candles without a BOS",
                candle_index=candle_index,
            )
            return

        bos = detect_post_choch_bos(candles, swings, stored_choch)
        if bos is None:
            return

        machine.transition(
            SetupState.RETEST_WAITING,
            event=bos,
            reason=f"post-CHoCH {bos.direction} BOS recognized, awaiting confirmation",
            candle_index=candle_index,
        )
        machine.context = (bos, matching_return)
        return

    if machine.state == SetupState.RETEST_WAITING:
        bos, matching_return = machine.context

        if has_level_been_lost(
            candle, bos.broken_level, bos.direction, policy, tolerance
        ):
            machine.transition(
                SetupState.INVALIDATED,
                event=candle,
                reason=f"level {bos.broken_level} lost under {policy.value} policy",
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

        signal = detect_liquidity_sweep_signal(candles, swings, external, scope=scope)
        if signal is None:
            return

        machine.transition(
            SetupState.CONFIRMATION_WAITING,
            event=signal,
            reason=f"{signal.confirmation_pattern} confirmation detected",
            candle_index=candle_index,
        )
        machine.transition(
            SetupState.VALID_SETUP,
            event=signal,
            reason=f"{signal.confirmation_pattern} confirmation accepted",
            candle_index=candle_index,
        )
        machine.context = signal
        return
