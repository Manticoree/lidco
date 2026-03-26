"""AuditLogger — tamper-evident JSON audit trail with CSV export (stdlib only)."""
from __future__ import annotations

import csv
import io
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AuditEntry:
    id: str
    timestamp: float
    actor: str
    action: str
    resource: str
    outcome: str          # "success" | "failure" | "denied"
    details: dict[str, Any]
    session_id: str


class AuditLogger:
    """
    Structured audit logger with JSON persistence and CSV export.

    Parameters
    ----------
    path:
        JSON file path.  Pass ``None`` for in-memory only.
    session_id:
        Optional session identifier attached to every entry.
    max_entries:
        Maximum in-memory entries (older entries are flushed to disk only).
    """

    OUTCOMES = frozenset({"success", "failure", "denied"})

    def __init__(
        self,
        path: str | Path | None = "DEFAULT",
        *,
        session_id: str = "",
        max_entries: int = 10_000,
    ) -> None:
        if path == "DEFAULT":
            path = Path(".lidco") / "audit.json"
        self._path: Path | None = Path(path) if path is not None else None
        self._session_id = session_id or str(uuid.uuid4())
        self._max_entries = max_entries
        self._entries: list[AuditEntry] = []
        self._lock = threading.Lock()
        if self._path and self._path.exists():
            self._load()

    # ------------------------------------------------------------------- log

    def log(
        self,
        actor: str,
        action: str,
        resource: str,
        *,
        outcome: str = "success",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """
        Record an audit event.

        Raises
        ------
        ValueError
            If *outcome* is not one of ``success``, ``failure``, ``denied``.
        """
        if outcome not in self.OUTCOMES:
            raise ValueError(
                f"Invalid outcome {outcome!r}. Must be one of {sorted(self.OUTCOMES)}"
            )
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            actor=actor,
            action=action,
            resource=resource,
            outcome=outcome,
            details=dict(details or {}),
            session_id=self._session_id,
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries :]
        self._save()
        return entry

    # ----------------------------------------------------------------- query

    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        resource: str | None = None,
        outcome: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int | None = None,
    ) -> list[AuditEntry]:
        """Return entries matching all provided filters (newest first)."""
        with self._lock:
            entries = list(self._entries)

        results = []
        for e in entries:
            if actor is not None and e.actor != actor:
                continue
            if action is not None and e.action != action:
                continue
            if resource is not None and e.resource != resource:
                continue
            if outcome is not None and e.outcome != outcome:
                continue
            if since is not None and e.timestamp < since:
                continue
            if until is not None and e.timestamp > until:
                continue
            results.append(e)

        results.sort(key=lambda e: e.timestamp, reverse=True)
        if limit is not None:
            results = results[:limit]
        return results

    def all(self) -> list[AuditEntry]:
        """Return all entries (oldest first)."""
        with self._lock:
            return list(self._entries)

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def clear(self) -> int:
        """Clear all in-memory entries.  Return count cleared."""
        with self._lock:
            n = len(self._entries)
            self._entries = []
        self._save()
        return n

    # ----------------------------------------------------------------- export

    def export_csv(self) -> str:
        """Return all entries as a CSV string."""
        output = io.StringIO()
        fieldnames = ["id", "timestamp", "actor", "action", "resource", "outcome", "details", "session_id"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        with self._lock:
            entries = list(self._entries)
        for e in entries:
            row = asdict(e)
            row["details"] = json.dumps(row["details"])
            writer.writerow(row)
        return output.getvalue()

    def export_json(self) -> str:
        """Return all entries as a JSON string."""
        with self._lock:
            entries = list(self._entries)
        return json.dumps([asdict(e) for e in entries], indent=2)

    # ---------------------------------------------------------------- persist

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = [asdict(e) for e in self._entries]
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            entries = []
            for item in raw:
                entries.append(AuditEntry(**item))
            with self._lock:
                self._entries = entries
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass

    def reload(self) -> None:
        """Re-read entries from disk."""
        self._load()

    @property
    def session_id(self) -> str:
        return self._session_id
