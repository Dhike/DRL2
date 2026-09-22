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

    def transition(self, new_state: SetupState, event: object, reason: str) -> None:
        """Move to `new_state` and record the transition.

        Generic for now -- the domain rules for which event justifies
        which transition are added in later steps.
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
