"""Orchestrate automatic context compaction based on utilization thresholds."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time


class CompactionTrigger(str, Enum):
    """Reason a compaction was triggered."""

    THRESHOLD = "threshold"
    MANUAL = "manual"
    PRE_CALL = "pre_call"
    EMERGENCY = "emergency"


@dataclass(frozen=True)
class CompactionEvent:
    """Record of a single compaction operation."""

    trigger: CompactionTrigger
    before_tokens: int = 0
    after_tokens: int = 0
    strategy: str = ""
    timestamp: float = field(default_factory=time.time)
    messages_affected: int = 0


class CompactionOrchestrator:
    """Decide *when* and *how* to compact context automatically."""

    def __init__(
        self,
        warn_threshold: float = 0.70,
        critical_threshold: float = 0.85,
        emergency_threshold: float = 0.95,
    ) -> None:
        self._warn = warn_threshold
        self._critical = critical_threshold
        self._emergency = emergency_threshold
        self._events: list[CompactionEvent] = []
        self._enabled: bool = True

    # -- query ----------------------------------------------------------------

    def should_compact(self, utilization: float) -> CompactionTrigger | None:
        """Return the trigger type if compaction needed, else ``None``."""
        if not self._enabled:
            return None
        if utilization >= self._emergency:
            return CompactionTrigger.EMERGENCY
        if utilization >= self._critical:
            return CompactionTrigger.PRE_CALL
        if utilization >= self._warn:
            return CompactionTrigger.THRESHOLD
        return None

    def select_strategy(self, utilization: float) -> str:
        """Pick a compaction strategy based on current utilization."""
        if utilization < self._critical:
            return "trim_old_tool_results"
        if utilization < self._emergency:
            return "summarize_middle"
        return "aggressive_prune"

    # -- record ---------------------------------------------------------------

    def record_compaction(
        self,
        trigger: CompactionTrigger,
        before: int,
        after: int,
        strategy: str,
        messages_affected: int = 0,
    ) -> CompactionEvent:
        """Log a compaction event and return it."""
        event = CompactionEvent(
            trigger=trigger,
            before_tokens=before,
            after_tokens=after,
            strategy=strategy,
            messages_affected=messages_affected,
        )
        self._events = [*self._events, event]
        return event

    # -- accessors ------------------------------------------------------------

    def get_events(self, limit: int = 20) -> list[CompactionEvent]:
        """Return the most recent *limit* events."""
        return list(self._events[-limit:])

    def total_saved(self) -> int:
        """Total tokens reclaimed across all compactions."""
        return sum(e.before_tokens - e.after_tokens for e in self._events)

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    def summary(self) -> str:
        """Human-readable summary."""
        if not self._events:
            return "Compaction: no events recorded."
        return (
            f"Compaction: {len(self._events)} events, "
            f"{self.total_saved()} tokens saved, "
            f"enabled={self._enabled}"
        )
