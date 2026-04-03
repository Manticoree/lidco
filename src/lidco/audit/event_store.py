"""AuditEventStore — Immutable event log with tamper detection, export, and retention."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit event with integrity checksum."""

    id: str
    event_type: str
    actor: str
    action: str
    resource: str
    timestamp: float
    metadata: dict[str, Any]
    checksum: str = ""


def _compute_checksum(event_type: str, actor: str, action: str, resource: str, timestamp: float) -> str:
    """Compute SHA-256 checksum from event fields."""
    payload = f"{event_type}|{actor}|{action}|{resource}|{timestamp}"
    return hashlib.sha256(payload.encode()).hexdigest()


class AuditEventStore:
    """Immutable event log with tamper detection, export, and retention.

    Parameters
    ----------
    max_events:
        Maximum events to retain in memory.
    """

    def __init__(self, max_events: int = 100_000) -> None:
        self._max_events = max_events
        self._events: list[AuditEvent] = []
        self._index: dict[str, AuditEvent] = {}

    # ---------------------------------------------------------------- append

    def append(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Create and store a new audit event with integrity checksum."""
        ts = time.time()
        checksum = _compute_checksum(event_type, actor, action, resource, ts)
        event = AuditEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            actor=actor,
            action=action,
            resource=resource,
            timestamp=ts,
            metadata=dict(metadata or {}),
            checksum=checksum,
        )
        self._events.append(event)
        self._index[event.id] = event
        # Enforce retention limit
        if len(self._events) > self._max_events:
            removed = self._events[: len(self._events) - self._max_events]
            self._events = self._events[-self._max_events:]
            for r in removed:
                self._index.pop(r.id, None)
        return event

    # ---------------------------------------------------------------- get

    def get(self, event_id: str) -> AuditEvent | None:
        """Look up an event by ID."""
        return self._index.get(event_id)

    # ---------------------------------------------------------------- verify

    def verify(self, event: AuditEvent) -> bool:
        """Verify that an event's checksum matches its fields."""
        expected = _compute_checksum(
            event.event_type, event.actor, event.action, event.resource, event.timestamp
        )
        return event.checksum == expected

    def verify_all(self) -> tuple[int, int]:
        """Verify all events. Return (valid_count, invalid_count)."""
        valid = 0
        invalid = 0
        for event in self._events:
            if self.verify(event):
                valid += 1
            else:
                invalid += 1
        return valid, invalid

    # ---------------------------------------------------------------- export

    def export(self, format: str = "json") -> str:
        """Export events as JSON or CSV string."""
        if format == "csv":
            return self._export_csv()
        return self._export_json()

    def _export_json(self) -> str:
        return json.dumps([asdict(e) for e in self._events], indent=2)

    def _export_csv(self) -> str:
        output = io.StringIO()
        fieldnames = ["id", "event_type", "actor", "action", "resource", "timestamp", "metadata", "checksum"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for e in self._events:
            row = asdict(e)
            row["metadata"] = json.dumps(row["metadata"])
            writer.writerow(row)
        return output.getvalue()

    # ---------------------------------------------------------------- access

    def events(self) -> list[AuditEvent]:
        """Return a copy of all events."""
        return list(self._events)

    def count(self) -> int:
        """Return the number of stored events."""
        return len(self._events)

    # ---------------------------------------------------------------- clear

    def clear(self, older_than: float | None = None) -> int:
        """Clear events. If *older_than* given, only remove events before that timestamp."""
        if older_than is None:
            n = len(self._events)
            self._events = []
            self._index = {}
            return n
        kept: list[AuditEvent] = []
        removed = 0
        for e in self._events:
            if e.timestamp < older_than:
                self._index.pop(e.id, None)
                removed += 1
            else:
                kept.append(e)
        self._events = kept
        return removed

    # ---------------------------------------------------------------- summary

    def summary(self) -> dict[str, Any]:
        """Return a summary dict of the event store."""
        actors: set[str] = set()
        actions: set[str] = set()
        event_types: set[str] = set()
        for e in self._events:
            actors.add(e.actor)
            actions.add(e.action)
            event_types.add(e.event_type)
        return {
            "total_events": len(self._events),
            "unique_actors": len(actors),
            "unique_actions": len(actions),
            "unique_event_types": len(event_types),
            "max_events": self._max_events,
        }
