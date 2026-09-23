"""Per-symbol/timeframe/strategy setup state machine.

The scanner strategies answer "what happened in the market?" -- this
module answers "given what happened, what state is this setup now in?"
It never derives new market facts itself.

Every state machine belongs to exactly one Scope (symbol, timeframe,
strategy). The StateMachineRegistry guarantees one instance per scope,
so one symbol's events can never mutate another's state.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.market.models import Candle
from app.scanner.level_loss import LevelLossPolicy, has_level_been_lost
from app.scanner.models import ScannerStrategy


class SetupState(StrEnum):
    IDLE = "idle"
    BREAK_DETECTED = "break_detected"
    RETEST_WAITING = "retest_waiting"
    CONFIRMATION_WAITING = "confirmation_waiting"
    VALID_SETUP = "valid_setup"
    TRIGGERED = "triggered"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


# Setups that are still "waiting" for the next stage; these are the only
# states that can go stale and expire.
WAITING_STATES = (
    SetupState.BREAK_DETECTED,
    SetupState.RETEST_WAITING,
    SetupState.CONFIRMATION_WAITING,
)

# Waiting states plus a confirmed-but-not-yet-triggered setup: all of
# these still depend on a structural level that can be lost.
AT_RISK_OF_LEVEL_LOSS = WAITING_STATES + (SetupState.VALID_SETUP,)


@dataclass(frozen=True)
class Scope:
    symbol: str
    timeframe: str
    strategy: ScannerStrategy


@dataclass(frozen=True)
class TransitionRecord:
    previous_state: SetupState
    event: object
    reason: str
    new_state: SetupState


@dataclass
class SetupStateMachine:
    scope: Scope
    state: SetupState = SetupState.IDLE
    history: list[TransitionRecord] = field(default_factory=list)
    state_entered_at: int | None = None
    context: object | None = None

    def transition(
        self,
        new_state: SetupState,
        event: object,
        reason: str,
        candle_index: int | None = None,
    ) -> None:
        """Move to `new_state` and record the transition.

        Generic for now -- the domain rules for which event justifies
        which transition live in the strategies and the checks below.
        If `candle_index` is given, it becomes the index at which this
        new state was entered, which expiry checks rely on.
        """
        self.history.append(
            TransitionRecord(
                previous_state=self.state,
                event=event,
                reason=reason,
                new_state=new_state,
            )
        )
        self.state = new_state
        if candle_index is not None:
            self.state_entered_at = candle_index

    def check_level_loss(
        self,
        candle: Candle,
        level: float,
        direction: str,
        policy: LevelLossPolicy,
        tolerance: float = 0.0,
        candle_index: int | None = None,
    ) -> bool:
        """If the setup's level has been lost, invalidate it.

        No-op outside the states that depend on a level. Returns True if
        this call caused an invalidation.
        """
        if self.state not in AT_RISK_OF_LEVEL_LOSS:
            return False

        if not has_level_been_lost(candle, level, direction, policy, tolerance):
            return False

        self.transition(
            SetupState.INVALIDATED,
            event=candle,
            reason=f"level {level} lost under {policy.value} policy",
            candle_index=candle_index,
        )
        return True

    def check_expiry(self, candle_index: int, max_bars: int = 20) -> bool:
        """If a waiting setup has gone `max_bars` candles without progress, expire it.

        No-op outside the waiting states, and if the entry candle index
        is unknown. Returns True if this call caused an expiry.
        """
        if self.state not in WAITING_STATES:
            return False

        if self.state_entered_at is None:
            return False

        if candle_index - self.state_entered_at < max_bars:
            return False

        self.transition(
            SetupState.EXPIRED,
            event=None,
            reason=f"expired after {max_bars} candles without progress",
            candle_index=candle_index,
        )
        return True


class StateMachineRegistry:
    """One SetupStateMachine per Scope. Never shared, never global."""

    def __init__(self) -> None:
        self._machines: dict[Scope, SetupStateMachine] = {}

    def get(self, scope: Scope) -> SetupStateMachine:
        if scope not in self._machines:
            self._machines[scope] = SetupStateMachine(scope=scope)
        return self._machines[scope]

    def scopes(self) -> list[Scope]:
        return list(self._machines.keys())
