"""Notification history — log, search, dismiss, snooze, export."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class HistoryEntry:
    """A single notification history entry."""

    id: str
    title: str
    message: str
    level: str
    timestamp: float
    dismissed: bool = False
    snoozed_until: float | None = None


class NotificationHistory:
    """Stores and manages notification history entries."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._max_entries = max_entries
        self._entries: list[HistoryEntry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, title: str, message: str, level: str = "info") -> HistoryEntry:
        entry = HistoryEntry(
            id=uuid.uuid4().hex[:12],
            title=title,
            message=message,
            level=level,
            timestamp=time.time(),
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
        return entry

    def get(self, entry_id: str) -> HistoryEntry | None:
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    def dismiss(self, entry_id: str) -> bool:
        entry = self.get(entry_id)
        if entry is None:
            return False
        entry.dismissed = True
        return True

    def snooze(self, entry_id: str, seconds: float) -> bool:
        entry = self.get(entry_id)
        if entry is None:
            return False
        entry.snoozed_until = time.time() + seconds
        return True

    def search(self, query: str) -> list[HistoryEntry]:
        q = query.lower()
        return [
            e
            for e in self._entries
            if q in e.title.lower() or q in e.message.lower()
        ]

    def undismissed(self) -> list[HistoryEntry]:
        now = time.time()
        return [
            e
            for e in self._entries
            if not e.dismissed
            and (e.snoozed_until is None or now >= e.snoozed_until)
        ]

    def clear(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        return count

    def export(self, format: str = "json") -> str:
        data = [
            {
                "id": e.id,
                "title": e.title,
                "message": e.message,
                "level": e.level,
                "timestamp": e.timestamp,
                "dismissed": e.dismissed,
                "snoozed_until": e.snoozed_until,
            }
            for e in self._entries
        ]
        if format == "json":
            return json.dumps(data, indent=2)
        # CSV fallback
        if not data:
            return "id,title,message,level,timestamp,dismissed,snoozed_until"
        lines = ["id,title,message,level,timestamp,dismissed,snoozed_until"]
        for d in data:
            lines.append(
                f"{d['id']},{d['title']},{d['message']},{d['level']},"
                f"{d['timestamp']},{d['dismissed']},{d['snoozed_until']}"
            )
        return "\n".join(lines)

    def all_entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def summary(self) -> dict:
        return {
            "total": len(self._entries),
            "dismissed": sum(1 for e in self._entries if e.dismissed),
            "undismissed": len(self.undismissed()),
            "max_entries": self._max_entries,
        }
