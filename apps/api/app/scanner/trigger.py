"""Stop-loss and take-profit trigger checks: a VALID_SETUP that has
either level hit by a candle's wick transitions to TRIGGERED.

Per user's explicit decision, TRIGGERED represents a CLOSING lifecycle
event for a confirmed setup -- entirely inside analysis, not execution.
Both checks are WICK-based (candle.low/high), not close-based, since a
real stop-loss or take-profit order fires on intrabar touch.

When a single candle's wick could plausibly have hit both levels, which
one is assumed to have happened first cannot be known from OHLC data
alone. `check_trigger`'s `tie_break` parameter controls this: user's
explicit choice is "stop_first" as the default (the conservative
assumption -- never assume the win when it can't be proven), with
"target_first" available as the alternative.
"""

from app.market.models import Candle
from app.scanner.break_and_retest import BreakAndRetestSignal
from app.scanner.liquidity_sweep import LiquiditySweepSignal
from app.scanner.risk import compute_take_profit
from app.scanner.state_machine import SetupState, SetupStateMachine
from app.scanner.trend_continuation import TrendContinuationConfirmation


def _direction_entry_stop(context: object) -> tuple[str, float, float] | None:
    """Extract (direction, entry_price, stop_loss) from whichever
    strategy's context object is currently stored, regardless of shape."""
    if isinstance(context, TrendContinuationConfirmation):
        confirmation = context
        candle = confirmation.candle
        retest_candle = confirmation.retest.candle
        entry_price = candle.close
        if confirmation.direction == "bullish":
            stop_loss = min(retest_candle.low, candle.low)
        else:
            stop_loss = max(retest_candle.high, candle.high)
        return confirmation.direction, entry_price, stop_loss

    if isinstance(context, (BreakAndRetestSignal, LiquiditySweepSignal)):
        return context.direction, context.entry_price, context.stop_loss

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

    extracted = _direction_entry_stop(machine.context)
    if extracted is None:
        return False
    direction, _entry_price, stop_loss = extracted

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


def check_target_hit(
    machine: SetupStateMachine,
    candle: Candle,
    candle_index: int,
    risk_reward: float,
) -> bool:
    """If `machine` is a VALID_SETUP whose take-profit (computed at a
    fixed `risk_reward` ratio) this candle's wick has reached, transition
    it to TRIGGERED. Returns True if it did."""
    if machine.state is not SetupState.VALID_SETUP:
        return False

    extracted = _direction_entry_stop(machine.context)
    if extracted is None:
        return False
    direction, entry_price, stop_loss = extracted

    try:
        take_profit = compute_take_profit(direction, entry_price, stop_loss, risk_reward)
    except ValueError:
        return False

    if direction == "bullish":
        hit = candle.high >= take_profit
    elif direction == "bearish":
        hit = candle.low <= take_profit
    else:
        return False

    if not hit:
        return False

    machine.transition(
        SetupState.TRIGGERED,
        event=candle,
        reason=f"take-profit {take_profit} hit",
        candle_index=candle_index,
    )
    return True


def check_trigger(
    machine: SetupStateMachine,
    candle: Candle,
    candle_index: int,
    risk_reward: float | None = None,
    tie_break: str = "stop_first",
) -> bool:
    """Check both the stop-loss and (if `risk_reward` is given) the
    take-profit for a VALID_SETUP, in the order `tie_break` specifies
    when a single candle's wick could plausibly hit both. Returns True
    if either fired."""
    if tie_break not in ("stop_first", "target_first"):
        raise ValueError(f"Unknown tie_break: {tie_break!r}")

    checks = [lambda: check_stop_hit(machine, candle, candle_index)]
    if risk_reward is not None:
        target_check = lambda: check_target_hit(machine, candle, candle_index, risk_reward)
        if tie_break == "target_first":
            checks.insert(0, target_check)
        else:
            checks.append(target_check)

    for check in checks:
        if check():
            return True
    return False
