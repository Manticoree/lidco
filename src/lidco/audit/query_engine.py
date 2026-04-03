"""AuditQueryEngine — Query, filter, aggregate, and timeline over audit events."""
from __future__ import annotations

import fnmatch
import json
from dataclasses import asdict, dataclass
from typing import Any

from lidco.audit.event_store import AuditEvent, AuditEventStore


@dataclass
class QueryFilter:
    """Filter criteria for audit queries."""

    actor: str | None = None
    action: str | None = None
    event_type: str | None = None
    resource_pattern: str | None = None
    since: float | None = None
    until: float | None = None


class AuditQueryEngine:
    """Query audit log with filtering, aggregation, and timeline.

    Parameters
    ----------
    store:
        The :class:`AuditEventStore` to query against.
    """

    def __init__(self, store: AuditEventStore) -> None:
        self._store = store

    # ---------------------------------------------------------------- helpers

    def _match(self, event: AuditEvent, f: QueryFilter) -> bool:
        if f.actor is not None and event.actor != f.actor:
            return False
        if f.action is not None and event.action != f.action:
            return False
        if f.event_type is not None and event.event_type != f.event_type:
            return False
        if f.resource_pattern is not None and not fnmatch.fnmatch(event.resource, f.resource_pattern):
            return False
        if f.since is not None and event.timestamp < f.since:
            return False
        if f.until is not None and event.timestamp > f.until:
            return False
        return True

    def _filtered(self, f: QueryFilter | None) -> list[AuditEvent]:
        events = self._store.events()
        if f is None:
            return events
        return [e for e in events if self._match(e, f)]

    # ---------------------------------------------------------------- query

    def query(self, filter: QueryFilter, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        """Return events matching *filter* with pagination."""
        matched = self._filtered(filter)
        return matched[offset: offset + limit]

    def count(self, filter: QueryFilter) -> int:
        """Count events matching *filter*."""
        return len(self._filtered(filter))

    # ---------------------------------------------------------------- aggregate

    def aggregate_by(self, field: str, filter: QueryFilter | None = None) -> dict[str, int]:
        """Count events grouped by *field* value."""
        events = self._filtered(filter)
        counts: dict[str, int] = {}
        for e in events:
            val = getattr(e, field, None)
            if val is None:
                continue
            key = str(val)
            counts[key] = counts.get(key, 0) + 1
        return counts

    # ---------------------------------------------------------------- timeline

    def timeline(self, filter: QueryFilter | None = None, bucket_minutes: int = 60) -> list[dict[str, Any]]:
        """Group events into time buckets. Returns [{bucket, count}]."""
        events = self._filtered(filter)
        if not events:
            return []
        bucket_seconds = bucket_minutes * 60
        buckets: dict[float, int] = {}
        for e in events:
            bucket_start = (e.timestamp // bucket_seconds) * bucket_seconds
            buckets[bucket_start] = buckets.get(bucket_start, 0) + 1
        result = []
        for ts in sorted(buckets):
            result.append({"bucket": ts, "count": buckets[ts]})
        return result

    # ---------------------------------------------------------------- unique lists

    def actors(self) -> list[str]:
        """Return unique actors across all events."""
        seen: set[str] = set()
        result: list[str] = []
        for e in self._store.events():
            if e.actor not in seen:
                seen.add(e.actor)
                result.append(e.actor)
        return result

    def actions(self) -> list[str]:
        """Return unique actions across all events."""
        seen: set[str] = set()
        result: list[str] = []
        for e in self._store.events():
            if e.action not in seen:
                seen.add(e.action)
                result.append(e.action)
        return result

    # ---------------------------------------------------------------- export

    def export(self, filter: QueryFilter, format: str = "json") -> str:
        """Export filtered events as JSON or CSV."""
        events = self._filtered(filter)
        if format == "csv":
            import csv
            import io

            output = io.StringIO()
            fieldnames = ["id", "event_type", "actor", "action", "resource", "timestamp", "metadata", "checksum"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for e in events:
                row = asdict(e)
                row["metadata"] = json.dumps(row["metadata"])
                writer.writerow(row)
            return output.getvalue()
        return json.dumps([asdict(e) for e in events], indent=2)
