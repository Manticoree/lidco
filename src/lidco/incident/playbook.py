"""Response playbooks — automated incident response steps."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from lidco.incident.detector import Incident


@dataclass(frozen=True)
class PlaybookStep:
    """Single step in a response playbook."""

    name: str
    action: str  # isolate / preserve / notify / block / log
    target: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PlaybookResult:
    """Result of executing a playbook."""

    incident_id: str
    steps_executed: int
    steps_failed: int
    actions_taken: list[str]
    timestamp: float


class ResponsePlaybook:
    """Manage and execute incident response playbooks."""

    def __init__(self) -> None:
        self._playbooks: dict[str, list[PlaybookStep]] = {}
        self._history: list[PlaybookResult] = []

    def register(self, incident_type: str, steps: list[PlaybookStep]) -> None:
        """Register a playbook for *incident_type*."""
        self._playbooks[incident_type] = list(steps)

    def execute(self, incident: Incident) -> PlaybookResult:
        """Execute the playbook matching *incident.type*."""
        steps = self._playbooks.get(incident.type, [])
        executed = 0
        failed = 0
        actions: list[str] = []
        for step in steps:
            try:
                actions.append(f"{step.action}:{step.target}")
                executed += 1
            except Exception:  # pragma: no cover
                failed += 1
        result = PlaybookResult(
            incident_id=incident.id,
            steps_executed=executed,
            steps_failed=failed,
            actions_taken=actions,
            timestamp=time.time(),
        )
        self._history.append(result)
        return result

    def get_playbook(self, incident_type: str) -> list[PlaybookStep] | None:
        """Return steps for *incident_type* or ``None``."""
        steps = self._playbooks.get(incident_type)
        return list(steps) if steps is not None else None

    def playbook_types(self) -> list[str]:
        """Return all registered incident types."""
        return sorted(self._playbooks)

    def history(self) -> list[PlaybookResult]:
        """Return execution history."""
        return list(self._history)

    def summary(self) -> dict:
        """Summary stats."""
        return {
            "registered_playbooks": len(self._playbooks),
            "total_executions": len(self._history),
            "types": self.playbook_types(),
        }
