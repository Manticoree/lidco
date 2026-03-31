"""Q145 Task 857: Command history with search and navigation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HistoryEntry:
    """A single command history entry."""

    command: str
    timestamp: float
    success: bool
    duration: Optional[float] = None


class CommandHistory:
    """Tracks executed commands with search and frequency analysis."""

    def __init__(self, max_entries: int = 500) -> None:
        self._max_entries = max_entries
        self._entries: list[HistoryEntry] = []

    def add(self, command: str, success: bool = True, duration: float = None) -> None:
        """Record a command execution."""
        entry = HistoryEntry(
            command=command,
            timestamp=time.time(),
            success=success,
            duration=duration,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

    def search(self, query: str) -> list[HistoryEntry]:
        """Return entries whose command contains *query* (substring match)."""
        q = query.lower()
        return [e for e in self._entries if q in e.command.lower()]

    def last(self, n: int = 10) -> list[HistoryEntry]:
        """Return the *n* most recent entries (newest first)."""
        return list(reversed(self._entries[-n:]))

    def get(self, index: int) -> Optional[HistoryEntry]:
        """Get entry by recency index (0 = most recent)."""
        if not self._entries or index < 0 or index >= len(self._entries):
            return None
        return self._entries[-(index + 1)]

    def frequent(self, n: int = 10) -> list[tuple[str, int]]:
        """Return the *n* most frequently used commands with counts."""
        counts: dict[str, int] = {}
        for e in self._entries:
            counts[e.command] = counts.get(e.command, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:n]

    def clear(self) -> None:
        """Remove all history entries."""
        self._entries.clear()

    @property
    def size(self) -> int:
        """Number of entries in history."""
        return len(self._entries)

    def undo_last(self) -> Optional[HistoryEntry]:
        """Pop and return the most recent entry, or None if empty."""
        if not self._entries:
            return None
        return self._entries.pop()
