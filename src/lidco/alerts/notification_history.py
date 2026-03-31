"""NotificationHistory — searchable, filterable notification archive (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lidco.alerts.notification_queue import Notification


@dataclass
class HistoryQuery:
    """Filter parameters for history queries."""

    level: Optional[str] = None
    source: Optional[str] = None
    since: Optional[float] = None
    until: Optional[float] = None
    limit: int = 50


class NotificationHistory:
    """Persistent notification history with querying and export.

    Parameters
    ----------
    max_entries:
        Maximum entries retained.  Oldest are dropped when full.
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._max_entries = max_entries
        self._entries: list[Notification] = []

    # ------------------------------------------------------------------ record

    def record(self, notification: Notification) -> None:
        """Store a notification in history."""
        self._entries.append(notification)
        while len(self._entries) > self._max_entries:
            self._entries.pop(0)

    # ------------------------------------------------------------------ query

    def query(self, q: Optional[HistoryQuery] = None) -> list[Notification]:
        """Filter history by query parameters.  ``None`` returns all (up to default limit)."""
        if q is None:
            q = HistoryQuery()
        results = self._entries
        if q.level is not None:
            results = [n for n in results if n.level == q.level]
        if q.source is not None:
            results = [n for n in results if n.source == q.source]
        if q.since is not None:
            results = [n for n in results if n.timestamp >= q.since]
        if q.until is not None:
            results = [n for n in results if n.timestamp <= q.until]
        return results[: q.limit]

    # ------------------------------------------------------------------ stats

    def stats(self) -> dict:
        """Return aggregate stats: counts by level, total, time range."""
        if not self._entries:
            return {"total": 0, "by_level": {}, "earliest": None, "latest": None}
        by_level: dict[str, int] = {}
        for n in self._entries:
            by_level[n.level] = by_level.get(n.level, 0) + 1
        return {
            "total": len(self._entries),
            "by_level": by_level,
            "earliest": self._entries[0].timestamp,
            "latest": self._entries[-1].timestamp,
        }

    # ------------------------------------------------------------------ export

    def export(self) -> list[dict]:
        """Return all entries as serializable dicts."""
        return [
            {
                "id": n.id,
                "level": n.level,
                "title": n.title,
                "message": n.message,
                "timestamp": n.timestamp,
                "read": n.read,
                "source": n.source,
            }
            for n in self._entries
        ]

    # ------------------------------------------------------------------ clear

    def clear(self, before: Optional[float] = None) -> None:
        """Clear entries.  If *before* is given, only remove entries older than that timestamp."""
        if before is None:
            self._entries.clear()
        else:
            self._entries = [n for n in self._entries if n.timestamp >= before]

    # ------------------------------------------------------------------ search

    def search(self, text: str) -> list[Notification]:
        """Search for *text* in title and message (case-insensitive)."""
        t = text.lower()
        return [
            n
            for n in self._entries
            if t in n.title.lower() or t in n.message.lower()
        ]
