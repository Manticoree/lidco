"""Cancel running agents with cascading and cleanup."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class CancelReason(str, Enum):
    """Why an agent was cancelled."""

    USER_REQUEST = "user_request"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    DEPENDENCY_FAILED = "dependency_failed"
    CASCADE = "cascade"


@dataclass(frozen=True)
class CancelRecord:
    """Record of a single cancellation."""

    agent_id: str
    reason: CancelReason
    timestamp: float = field(default_factory=time.time)
    cascade_from: str = ""


class CancellationManager:
    """Manage agent cancellations with cascading support."""

    def __init__(self, grace_period: float = 5.0) -> None:
        self._grace_period = grace_period
        self._records: tuple[CancelRecord, ...] = ()
        self._cancelled_ids: frozenset[str] = frozenset()

    @property
    def grace_period(self) -> float:
        return self._grace_period

    def cancel(
        self,
        agent_id: str,
        reason: CancelReason = CancelReason.USER_REQUEST,
    ) -> CancelRecord:
        """Cancel a single agent."""
        record = CancelRecord(agent_id=agent_id, reason=reason)
        self._records = (*self._records, record)
        self._cancelled_ids = self._cancelled_ids | {agent_id}
        return record

    def cascade_cancel(
        self,
        agent_id: str,
        dependents: list[str],
    ) -> list[CancelRecord]:
        """Cancel agent + all dependents with CASCADE reason."""
        records: list[CancelRecord] = []
        root = self.cancel(agent_id, CancelReason.USER_REQUEST)
        records = [root]
        for dep in dependents:
            rec = CancelRecord(
                agent_id=dep,
                reason=CancelReason.CASCADE,
                cascade_from=agent_id,
            )
            self._records = (*self._records, rec)
            self._cancelled_ids = self._cancelled_ids | {dep}
            records = [*records, rec]
        return records

    def is_cancelled(self, agent_id: str) -> bool:
        """Check if an agent has been cancelled."""
        return agent_id in self._cancelled_ids

    def get_cancelled(self) -> list[CancelRecord]:
        """Return all cancellation records."""
        return list(self._records)

    def clear(self) -> None:
        """Reset all cancellation state."""
        self._records = ()
        self._cancelled_ids = frozenset()

    def summary(self) -> str:
        """Human-readable summary."""
        if not self._records:
            return "No cancellations."
        lines = [f"Cancellations: {len(self._records)}"]
        for r in self._records:
            cascade = f" (from {r.cascade_from})" if r.cascade_from else ""
            lines = [*lines, f"  {r.agent_id}: {r.reason.value}{cascade}"]
        return "\n".join(lines)
