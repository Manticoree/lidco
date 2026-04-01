"""Log compaction events for debugging and undo."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid


@dataclass(frozen=True)
class JournalEntry:
    """Immutable record of one compaction operation."""

    id: str
    timestamp: float = field(default_factory=time.time)
    strategy: str = ""
    before_count: int = 0
    after_count: int = 0
    before_tokens: int = 0
    after_tokens: int = 0
    removed_indices: tuple[int, ...] = ()


class CompactionJournal:
    """Append-only journal of compaction operations."""

    def __init__(self, max_entries: int = 100) -> None:
        self._entries: list[JournalEntry] = []
        self._max = max_entries

    def log(
        self,
        strategy: str,
        before_count: int,
        after_count: int,
        before_tokens: int,
        after_tokens: int,
        removed_indices: tuple[int, ...] = (),
    ) -> JournalEntry:
        """Create a new journal entry and return it."""
        entry = JournalEntry(
            id=uuid.uuid4().hex[:12],
            strategy=strategy,
            before_count=before_count,
            after_count=after_count,
            before_tokens=before_tokens,
            after_tokens=after_tokens,
            removed_indices=removed_indices,
        )
        updated = [*self._entries, entry]
        if len(updated) > self._max:
            updated = updated[-self._max :]
        self._entries = updated
        return entry

    def get_entries(self, limit: int = 20) -> list[JournalEntry]:
        return list(self._entries[-limit:])

    def get_last(self) -> JournalEntry | None:
        return self._entries[-1] if self._entries else None

    def total_compactions(self) -> int:
        return len(self._entries)

    def total_tokens_saved(self) -> int:
        return sum(e.before_tokens - e.after_tokens for e in self._entries)

    def clear(self) -> None:
        self._entries = []

    def export(self) -> list[dict]:
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "strategy": e.strategy,
                "before_count": e.before_count,
                "after_count": e.after_count,
                "before_tokens": e.before_tokens,
                "after_tokens": e.after_tokens,
                "removed_indices": list(e.removed_indices),
            }
            for e in self._entries
        ]

    def summary(self) -> str:
        if not self._entries:
            return "Journal: empty."
        return (
            f"Journal: {len(self._entries)} entries, "
            f"{self.total_tokens_saved()} tokens saved."
        )
