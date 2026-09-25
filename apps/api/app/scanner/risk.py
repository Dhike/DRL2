"""Risk-management helpers, deliberately kept OUTSIDE the strategy
engines themselves (each engine's own docstring already states this
boundary: "Risk management and final order execution remain outside
this strategy engine.").

Take-profit is optional and configurable, per user's design: a fixed
1:2 risk-reward ratio is used for scanning (manual or automatic), while
live trading will later let the user choose their own ratio or a
swing-point-based target. Swing-point-based targets are NOT built here
-- deferred, since picking which structural swing to target is a
separate, harder design question.
"""


def compute_take_profit(
    direction: str,
    entry_price: float,
    stop_loss: float,
    risk_reward: float = 2.0,
) -> float:
    """
    Compute a take-profit price at a fixed risk-reward ratio from the
    entry and stop-loss.

    For a bullish setup, risk = entry - stop_loss (must be positive:
    the stop must be below entry); target = entry + risk * risk_reward.
    Bearish mirrors this (stop above entry).
    """
    if risk_reward <= 0:
        raise ValueError(f"risk_reward must be positive, got {risk_reward!r}")

    if direction == "bullish":
        risk = entry_price - stop_loss
        if risk <= 0:
            raise ValueError(
                "A bullish setup's stop_loss must be below its entry_price "
                f"(entry={entry_price}, stop_loss={stop_loss})"
            )
        return entry_price + risk * risk_reward

    if direction == "bearish":
        risk = stop_loss - entry_price
        if risk <= 0:
            raise ValueError(
                "A bearish setup's stop_loss must be above its entry_price "
                f"(entry={entry_price}, stop_loss={stop_loss})"
            )
        return entry_price - risk * risk_reward

    raise ValueError(f"Unknown direction: {direction!r}")
