"""EventStore — append-only event log with versioning and snapshots (stdlib only)."""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DomainEvent:
    """A domain event with aggregate identity, version, and payload."""
    event_id: str
    aggregate_id: str
    aggregate_type: str
    event_type: str
    version: int
    timestamp: float
    payload: dict[str, Any]

    @classmethod
    def create(
        cls,
        aggregate_id: str,
        aggregate_type: str,
        event_type: str,
        version: int,
        payload: dict[str, Any] | None = None,
    ) -> "DomainEvent":
        return cls(
            event_id=str(uuid.uuid4()),
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            event_type=event_type,
            version=version,
            timestamp=time.time(),
            payload=dict(payload or {}),
        )


@dataclass
class Snapshot:
    aggregate_id: str
    aggregate_type: str
    version: int
    timestamp: float
    state: dict[str, Any]


class OptimisticConcurrencyError(Exception):
    """Raised when an expected version does not match current version."""
    def __init__(self, aggregate_id: str, expected: int, actual: int) -> None:
        super().__init__(
            f"Concurrency conflict for {aggregate_id!r}: "
            f"expected version {expected}, got {actual}"
        )
        self.aggregate_id = aggregate_id
        self.expected = expected
        self.actual = actual


class EventStore:
    """
    Append-only event store with optimistic concurrency control.

    Parameters
    ----------
    path:
        JSON file for persistence.  Pass ``None`` for in-memory only.
    """

    def __init__(self, path: str | Path | None = "DEFAULT") -> None:
        if path == "DEFAULT":
            path = Path(".lidco") / "event_store.json"
        self._path: Path | None = Path(path) if path is not None else None
        self._events: list[DomainEvent] = []
        self._snapshots: dict[str, Snapshot] = {}
        self._lock = threading.Lock()
        if self._path and self._path.exists():
            self._load()

    # ------------------------------------------------------------------ append

    def append(
        self,
        event: DomainEvent,
        expected_version: int | None = None,
    ) -> None:
        """
        Append *event* to the store.

        Parameters
        ----------
        expected_version:
            If provided, raises :exc:`OptimisticConcurrencyError` if the
            current version for the aggregate differs.
        """
        with self._lock:
            if expected_version is not None:
                current = self._current_version(event.aggregate_id)
                if current != expected_version:
                    raise OptimisticConcurrencyError(
                        event.aggregate_id, expected_version, current
                    )
            self._events = [*self._events, event]
        self._save()

    def append_many(
        self,
        events: list[DomainEvent],
        expected_version: int | None = None,
    ) -> None:
        """Atomically append multiple events."""
        if not events:
            return
        with self._lock:
            if expected_version is not None:
                agg_id = events[0].aggregate_id
                current = self._current_version(agg_id)
                if current != expected_version:
                    raise OptimisticConcurrencyError(agg_id, expected_version, current)
            self._events = [*self._events, *events]
        self._save()

    # ------------------------------------------------------------------- query

    def load(self, aggregate_id: str) -> list[DomainEvent]:
        """Return all events for an aggregate (oldest first)."""
        with self._lock:
            return [e for e in self._events if e.aggregate_id == aggregate_id]

    def load_from_version(self, aggregate_id: str, from_version: int) -> list[DomainEvent]:
        """Return events for *aggregate_id* with version >= *from_version*."""
        with self._lock:
            return [
                e for e in self._events
                if e.aggregate_id == aggregate_id and e.version >= from_version
            ]

    def load_by_type(self, event_type: str) -> list[DomainEvent]:
        """Return all events of a given type across all aggregates."""
        with self._lock:
            return [e for e in self._events if e.event_type == event_type]

    def get_all(self) -> list[DomainEvent]:
        with self._lock:
            return list(self._events)

    def current_version(self, aggregate_id: str) -> int:
        with self._lock:
            return self._current_version(aggregate_id)

    def _current_version(self, aggregate_id: str) -> int:
        versions = [e.version for e in self._events if e.aggregate_id == aggregate_id]
        return max(versions) if versions else 0

    # --------------------------------------------------------------- snapshots

    def save_snapshot(self, snapshot: Snapshot) -> None:
        with self._lock:
            self._snapshots = {**self._snapshots, snapshot.aggregate_id: snapshot}
        self._save()

    def get_snapshot(self, aggregate_id: str) -> Snapshot | None:
        with self._lock:
            return self._snapshots.get(aggregate_id)

    # ------------------------------------------------------------------ persist

    def count(self) -> int:
        with self._lock:
            return len(self._events)

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = {
                    "events": [asdict(e) for e in self._events],
                    "snapshots": {
                        k: asdict(v) for k, v in self._snapshots.items()
                    },
                }
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            events = [DomainEvent(**e) for e in raw.get("events", [])]
            snapshots = {
                k: Snapshot(**v) for k, v in raw.get("snapshots", {}).items()
            }
            with self._lock:
                self._events = events
                self._snapshots = snapshots
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass

    def clear(self) -> None:
        with self._lock:
            self._events = []
            self._snapshots = {}
        self._save()
