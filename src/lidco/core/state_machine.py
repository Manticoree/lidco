"""StateMachine — finite state machine (stdlib only)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


class InvalidTransition(Exception):
    """Raised when no valid transition exists from current state for given trigger."""

    def __init__(self, state: str, trigger: str) -> None:
        super().__init__(f"No valid transition from state {state!r} on trigger {trigger!r}")
        self.state = state
        self.trigger = trigger


@dataclass
class State:
    name: str

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, State):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return NotImplemented


@dataclass
class Transition:
    from_state: str
    to_state: str
    trigger: str
    guard: Callable[[], bool] | None = None
    action: Callable[[], None] | None = None


@dataclass
class HistoryEntry:
    from_state: str
    to_state: str
    trigger: str
    timestamp: float = field(default_factory=time.time)


class StateMachine:
    """
    Finite state machine with guard conditions and entry actions.

    Parameters
    ----------
    initial_state:
        Name of the starting state.
    """

    def __init__(self, initial_state: str) -> None:
        self._initial = initial_state
        self._current = initial_state
        self._transitions: list[Transition] = []
        self._history: list[HistoryEntry] = []
        self._states: set[str] = {initial_state}

    # ----------------------------------------------------------------- config

    def add_state(self, name: str) -> None:
        """Register a state explicitly."""
        self._states.add(name)

    def add_transition(
        self,
        from_state: str,
        to_state: str,
        trigger: str,
        guard: Callable[[], bool] | None = None,
        action: Callable[[], None] | None = None,
    ) -> None:
        """Register a transition.  Auto-registers both states."""
        self._states.add(from_state)
        self._states.add(to_state)
        self._transitions.append(
            Transition(
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
                guard=guard,
                action=action,
            )
        )

    # ----------------------------------------------------------------- runtime

    def trigger(self, event: str) -> str:
        """
        Fire *event* from current state.  Return new state name.

        Raises
        ------
        InvalidTransition
            If no matching transition exists or guard returns False.
        """
        for t in self._transitions:
            if t.from_state == self._current and t.trigger == event:
                if t.guard is not None and not t.guard():
                    continue
                old_state = self._current
                self._current = t.to_state
                self._history.append(
                    HistoryEntry(from_state=old_state, to_state=t.to_state, trigger=event)
                )
                if t.action is not None:
                    t.action()
                return self._current

        raise InvalidTransition(self._current, event)

    def can_trigger(self, event: str) -> bool:
        """Return True if a valid transition (with passing guard) exists for *event*."""
        for t in self._transitions:
            if t.from_state == self._current and t.trigger == event:
                if t.guard is None or t.guard():
                    return True
        return False

    def available_triggers(self) -> list[str]:
        """Return all triggers valid from current state."""
        seen: set[str] = set()
        result: list[str] = []
        for t in self._transitions:
            if t.from_state == self._current and t.trigger not in seen:
                if t.guard is None or t.guard():
                    seen.add(t.trigger)
                    result.append(t.trigger)
        return result

    def reset(self) -> None:
        """Return to initial state and clear history."""
        self._current = self._initial
        self._history = []

    # --------------------------------------------------------------- properties

    @property
    def current_state(self) -> str:
        return self._current

    @property
    def history(self) -> list[HistoryEntry]:
        return list(self._history)

    @property
    def states(self) -> set[str]:
        return set(self._states)
