"""Permission audit — log all permission decisions with query and export."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEntry:
    """A single permission audit entry."""

    id: str
    timestamp: float
    actor: str
    action: str
    scope: str
    resource: str
    reason: str
    result: str


class PermissionAudit:
    """Log all permission decisions with query and export."""

    def __init__(self, max_entries: int = 10000) -> None:
        self._max_entries = max_entries
        self._entries: list[AuditEntry] = []

    def log(
        self,
        actor: str,
        action: str,
        scope: str,
        resource: str,
        reason: str,
        result: str,
    ) -> AuditEntry:
        """Record an audit entry."""
        entry = AuditEntry(
            id=uuid.uuid4().hex[:12],
            timestamp=time.time(),
            actor=actor,
            action=action,
            scope=scope,
            resource=resource,
            reason=reason,
            result=result,
        )
        self._entries.append(entry)
        # Trim oldest if over limit
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
        return entry

    def query(
        self,
        actor: str | None = None,
        scope: str | None = None,
        result: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query entries with optional filters."""
        filtered = self._entries
        if actor is not None:
            filtered = [e for e in filtered if e.actor == actor]
        if scope is not None:
            filtered = [e for e in filtered if e.scope == scope]
        if result is not None:
            filtered = [e for e in filtered if e.result == result]
        if since is not None:
            filtered = [e for e in filtered if e.timestamp >= since]
        return filtered[-limit:]

    def export_json(self) -> str:
        """Export all entries as a JSON string."""
        data = [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "actor": e.actor,
                "action": e.action,
                "scope": e.scope,
                "resource": e.resource,
                "reason": e.reason,
                "result": e.result,
            }
            for e in self._entries
        ]
        return json.dumps(data, indent=2)

    def count(self) -> int:
        """Return the number of entries."""
        return len(self._entries)

    def clear(self) -> int:
        """Clear all entries. Returns count removed."""
        count = len(self._entries)
        self._entries.clear()
        return count

    def summary(self) -> dict:
        """Return summary statistics."""
        by_result: dict[str, int] = {}
        by_actor: dict[str, int] = {}
        for e in self._entries:
            by_result[e.result] = by_result.get(e.result, 0) + 1
            by_actor[e.actor] = by_actor.get(e.actor, 0) + 1
        return {
            "total": len(self._entries),
            "by_result": by_result,
            "by_actor": by_actor,
        }
