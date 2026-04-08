"""Config Audit — track config changes with who/when/why.

Rollback support and compliance reporting.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AuditAction(Enum):
    """Type of audited config action."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ROLLBACK = "rollback"


@dataclass(frozen=True)
class AuditEntry:
    """A single audit log entry."""

    timestamp: str
    action: AuditAction
    user: str
    config_name: str
    reason: str = ""
    changes: dict[str, Any] = field(default_factory=dict)
    snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComplianceReport:
    """Compliance report over a time period."""

    total_changes: int
    changes_by_user: dict[str, int] = field(default_factory=dict)
    changes_by_action: dict[str, int] = field(default_factory=dict)
    configs_modified: list[str] = field(default_factory=list)
    entries: list[AuditEntry] = field(default_factory=list)
    period_start: str = ""
    period_end: str = ""


class ConfigAudit:
    """Track config changes with full audit trail and rollback."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._snapshots: dict[str, list[dict[str, Any]]] = {}

    # -- Recording ---------------------------------------------------------

    def record(
        self,
        action: AuditAction,
        user: str,
        config_name: str,
        config_data: dict[str, Any],
        *,
        reason: str = "",
        changes: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Record a config change in the audit log."""
        now = datetime.now(timezone.utc).isoformat()
        snapshot = copy.deepcopy(config_data)
        entry = AuditEntry(
            timestamp=now,
            action=action,
            user=user,
            config_name=config_name,
            reason=reason,
            changes=dict(changes) if changes else {},
            snapshot=snapshot,
        )
        self._entries.append(entry)

        # Store snapshot for rollback
        self._snapshots.setdefault(config_name, []).append(snapshot)
        return entry

    # -- Querying ----------------------------------------------------------

    def get_history(self, config_name: str | None = None) -> list[AuditEntry]:
        """Return audit history, optionally filtered by config name."""
        if config_name is None:
            return list(self._entries)
        return [e for e in self._entries if e.config_name == config_name]

    def get_user_history(self, user: str) -> list[AuditEntry]:
        """Return audit entries by a specific user."""
        return [e for e in self._entries if e.user == user]

    def get_latest(self, config_name: str) -> AuditEntry | None:
        """Return the latest audit entry for a config."""
        entries = self.get_history(config_name)
        return entries[-1] if entries else None

    # -- Rollback ----------------------------------------------------------

    def rollback(self, config_name: str, user: str, *, reason: str = "") -> dict[str, Any] | None:
        """Roll back to the previous snapshot. Returns the restored config or None."""
        snapshots = self._snapshots.get(config_name, [])
        if len(snapshots) < 2:
            return None

        # Remove current, restore previous
        snapshots.pop()
        previous = copy.deepcopy(snapshots[-1])

        self.record(
            AuditAction.ROLLBACK,
            user,
            config_name,
            previous,
            reason=reason or "Rollback to previous version",
        )
        return previous

    def get_snapshot(self, config_name: str, version: int = -1) -> dict[str, Any] | None:
        """Return a snapshot by version index (0-based, or -1 for latest)."""
        snapshots = self._snapshots.get(config_name, [])
        if not snapshots:
            return None
        try:
            return copy.deepcopy(snapshots[version])
        except IndexError:
            return None

    def snapshot_count(self, config_name: str) -> int:
        """Return the number of snapshots for a config."""
        return len(self._snapshots.get(config_name, []))

    # -- Compliance --------------------------------------------------------

    def compliance_report(
        self,
        *,
        since: str | None = None,
        until: str | None = None,
    ) -> ComplianceReport:
        """Generate a compliance report over a time period."""
        entries = self._entries
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        if until:
            entries = [e for e in entries if e.timestamp <= until]

        by_user: dict[str, int] = {}
        by_action: dict[str, int] = {}
        configs: set[str] = set()

        for e in entries:
            by_user[e.user] = by_user.get(e.user, 0) + 1
            by_action[e.action.value] = by_action.get(e.action.value, 0) + 1
            configs.add(e.config_name)

        period_start = entries[0].timestamp if entries else ""
        period_end = entries[-1].timestamp if entries else ""

        return ComplianceReport(
            total_changes=len(entries),
            changes_by_user=by_user,
            changes_by_action=by_action,
            configs_modified=sorted(configs),
            entries=entries,
            period_start=period_start,
            period_end=period_end,
        )

    # -- Export ------------------------------------------------------------

    def export_json(self, config_name: str | None = None) -> str:
        """Export audit entries as JSON string."""
        entries = self.get_history(config_name)
        data = [
            {
                "timestamp": e.timestamp,
                "action": e.action.value,
                "user": e.user,
                "config_name": e.config_name,
                "reason": e.reason,
                "changes": e.changes,
            }
            for e in entries
        ]
        return json.dumps(data, indent=2)

    def clear(self) -> None:
        """Clear all audit data."""
        self._entries.clear()
        self._snapshots.clear()
