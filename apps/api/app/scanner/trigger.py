"""Stop-loss trigger check: a VALID_SETUP that has its stop-loss hit
transitions to TRIGGERED.

Per user's explicit decision, TRIGGERED represents a CLOSING lifecycle
event for a confirmed setup -- "did this setup's stop (or eventually,
take-profit) get hit afterward" -- entirely inside analysis, not
execution. Take-profit is currently always None on every strategy's
signal (no target logic exists yet), so today this can only ever fire
on a stop-loss hit; take-profit-hit detection is deferred until a
target rule is designed.

The check is WICK-based (candle.low/high), not close-based, per user's
explicit choice: a real stop-loss order fires the instant price
touches it intrabar, unlike the close-based convention used elsewhere
in this engine for structural checks (level loss, CHoCH).
"""

from app.market.models import Candle
from app.scanner.break_and_retest import BreakAndRetestSignal
from app.scanner.liquidity_sweep import LiquiditySweepSignal
from app.scanner.state_machine import SetupState, SetupStateMachine
from app.scanner.trend_continuation import TrendContinuationConfirmation


def _direction_and_stop(context: object) -> tuple[str, float] | None:
    if isinstance(context, TrendContinuationConfirmation):
        confirmation = context
        candle = confirmation.candle
        retest_candle = confirmation.retest.candle
        if confirmation.direction == "bullish":
            stop_loss = min(retest_candle.low, candle.low)
        else:
            stop_loss = max(retest_candle.high, candle.high)
        return confirmation.direction, stop_loss

    if isinstance(context, (BreakAndRetestSignal, LiquiditySweepSignal)):
        return context.direction, context.stop_loss

    return None


def check_stop_hit(
    machine: SetupStateMachine,
    candle: Candle,
    candle_index: int,
) -> bool:
    """If `machine` is a VALID_SETUP whose stop-loss this candle's wick
    has reached, transition it to TRIGGERED. Returns True if it did."""
    if machine.state is not SetupState.VALID_SETUP:
        return False

    extracted = _direction_and_stop(machine.context)
    if extracted is None:
        return False
    direction, stop_loss = extracted

    if direction == "bullish":
        hit = candle.low <= stop_loss
    elif direction == "bearish":
        hit = candle.high >= stop_loss
    else:
        return False

    if not hit:
        return False

    machine.transition(
        SetupState.TRIGGERED,
        event=candle,
        reason=f"stop-loss {stop_loss} hit",
        candle_index=candle_index,
    )
    return True
