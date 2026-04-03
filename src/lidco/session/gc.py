"""Session garbage collector — retention policies, archive, disk usage."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from lidco.session.persister import SessionPersister


@dataclass(frozen=True)
class GCResult:
    """Immutable result of a garbage-collection run."""

    deleted_count: int = 0
    freed_bytes: int = 0
    archived: list[str] = field(default_factory=list)


class SessionGarbageCollector:
    """Garbage-collect old or excess sessions from the persister."""

    def __init__(self, persister: SessionPersister) -> None:
        self._persister = persister
        self._retention_days: int | None = None
        self._max_count: int | None = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_retention(
        self,
        days: int | None = None,
        max_count: int | None = None,
    ) -> None:
        """Set retention policy.  Either or both may be ``None`` (no limit)."""
        self._retention_days = days
        self._max_count = max_count

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self) -> GCResult:
        """Delete sessions that violate the retention policy."""
        to_delete = self._candidates()
        if not to_delete:
            return GCResult()

        freed = 0
        archived: list[str] = []
        for sid in to_delete:
            freed += self._estimate_session_bytes(sid)
            self._persister.delete(sid)

        return GCResult(
            deleted_count=len(to_delete),
            freed_bytes=freed,
            archived=archived,
        )

    def dry_run(self) -> GCResult:
        """Show what *collect* would delete, without actually deleting."""
        to_delete = self._candidates()
        freed = sum(self._estimate_session_bytes(sid) for sid in to_delete)
        return GCResult(
            deleted_count=len(to_delete),
            freed_bytes=freed,
            archived=[],
        )

    def disk_usage(self) -> dict:
        """Return ``{total_sessions, total_bytes}`` (estimated)."""
        sessions = self._persister.list_sessions()
        total_bytes = sum(
            self._estimate_session_bytes(s["id"]) for s in sessions
        )
        return {
            "total_sessions": len(sessions),
            "total_bytes": total_bytes,
        }

    def archive(self, session_id: str) -> str:
        """Serialise a session to a JSON string and then delete it.

        Returns the JSON archive string (empty string if not found).
        """
        raw = self._persister.get_raw(session_id)
        if raw is None:
            return ""
        archive_str = json.dumps(raw, indent=2)
        self._persister.delete(session_id)
        return archive_str

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _candidates(self) -> list[str]:
        """Compute the set of session IDs to delete."""
        sessions = self._persister.list_sessions()  # sorted by updated_at desc
        to_delete: set[str] = set()

        # Age-based retention
        if self._retention_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
            cutoff_iso = cutoff.isoformat()
            for s in sessions:
                if s["updated_at"] < cutoff_iso:
                    to_delete.add(s["id"])

        # Count-based retention — keep newest *max_count*, delete the rest
        if self._max_count is not None and len(sessions) > self._max_count:
            excess = sessions[self._max_count:]
            for s in excess:
                to_delete.add(s["id"])

        return sorted(to_delete)

    def _estimate_session_bytes(self, session_id: str) -> int:
        """Rough byte-size estimate for a session row."""
        raw = self._persister.get_raw(session_id)
        if raw is None:
            return 0
        total = 0
        for value in raw.values():
            if value is not None:
                total += len(str(value).encode("utf-8"))
        return total
