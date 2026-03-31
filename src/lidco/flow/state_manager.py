"""Flow State Manager — tracks session-wide flow state."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from lidco.flow.action_tracker import ActionTracker
from lidco.flow.intent_inferrer import IntentInferrer


@dataclass
class FlowState:
    """Snapshot of flow state."""

    session_start: float
    total_actions: int
    current_intent: str
    intent_history: list[tuple[float, str]] = field(default_factory=list)
    productivity_score: float = 100.0


class FlowStateManager:
    """Manages the high-level flow state across a session."""

    def __init__(self, tracker: ActionTracker, inferrer: IntentInferrer) -> None:
        self._tracker = tracker
        self._inferrer = inferrer
        self._session_start: float = time.time()
        self._intent_history: list[tuple[float, str]] = []
        self._last_intent: str = ""

    def update(self) -> FlowState:
        """Recalculate and return the current flow state."""
        inferred = self._inferrer.infer()
        current_intent = inferred.intent

        if current_intent != self._last_intent:
            self._intent_history.append((time.time(), current_intent))
            self._last_intent = current_intent

        return FlowState(
            session_start=self._session_start,
            total_actions=len(self._tracker.recent(limit=9999)),
            current_intent=current_intent,
            intent_history=list(self._intent_history),
            productivity_score=self.productivity_score(),
        )

    def productivity_score(self) -> float:
        """(successful_actions / total_actions) * 100."""
        actions = self._tracker.recent(limit=9999)
        if not actions:
            return 100.0
        successful = sum(1 for a in actions if a.success)
        return round((successful / len(actions)) * 100, 1)

    def session_duration(self) -> float:
        """Seconds since session start."""
        return time.time() - self._session_start

    def intent_switches(self) -> int:
        """How many times the intent changed."""
        return max(0, len(self._intent_history) - 1) if self._intent_history else 0

    def export(self) -> dict:
        """Serialize state to a dict."""
        state = self.update()
        return {
            "session_start": state.session_start,
            "total_actions": state.total_actions,
            "current_intent": state.current_intent,
            "intent_history": state.intent_history,
            "productivity_score": state.productivity_score,
            "session_duration": self.session_duration(),
            "intent_switches": self.intent_switches(),
        }

    def import_state(self, data: dict) -> None:
        """Restore state from a dict."""
        self._session_start = data.get("session_start", self._session_start)
        self._intent_history = data.get("intent_history", [])
        self._last_intent = self._intent_history[-1][1] if self._intent_history else ""

    def summary(self) -> str:
        """Human-readable flow summary."""
        state = self.update()
        duration = self.session_duration()
        mins = int(duration // 60)
        secs = int(duration % 60)
        return (
            f"Session: {mins}m {secs}s | "
            f"Actions: {state.total_actions} | "
            f"Intent: {state.current_intent} | "
            f"Productivity: {state.productivity_score:.0f}% | "
            f"Intent switches: {self.intent_switches()}"
        )
