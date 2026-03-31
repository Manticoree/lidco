"""Crash journal for tracking in-flight actions and enabling recovery."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class JournalEntry:
    """A single journal entry tracking an in-flight action."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    action: str = ""
    state: dict = field(default_factory=dict)
    completed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "JournalEntry":
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            timestamp=data.get("timestamp", 0.0),
            action=data.get("action", ""),
            state=data.get("state", {}),
            completed=data.get("completed", False),
        )


class CrashJournal:
    """Write-ahead journal for crash recovery.

    Records actions before they execute so incomplete actions
    can be detected and recovered on restart.
    """

    def __init__(self, journal_dir: str) -> None:
        self._journal_dir = Path(journal_dir)
        self._journal_dir.mkdir(parents=True, exist_ok=True)
        self._journal_file = self._journal_dir / "journal.json"
        self._entries: dict[str, JournalEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load journal from disk."""
        if self._journal_file.exists():
            try:
                data = json.loads(self._journal_file.read_text(encoding="utf-8"))
                for entry_data in data:
                    entry = JournalEntry.from_dict(entry_data)
                    self._entries[entry.id] = entry
            except (json.JSONDecodeError, KeyError):
                self._entries = {}

    def _save(self) -> None:
        """Persist journal to disk."""
        data = [e.to_dict() for e in self._entries.values()]
        self._journal_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def write_entry(self, entry: JournalEntry) -> str:
        """Record an action before executing it. Returns the entry id."""
        self._entries[entry.id] = entry
        self._save()
        return entry.id

    def complete(self, entry_id: str) -> None:
        """Mark an entry as successfully completed."""
        if entry_id not in self._entries:
            raise KeyError(f"No journal entry with id {entry_id!r}")
        entry = self._entries[entry_id]
        self._entries[entry_id] = JournalEntry(
            id=entry.id,
            timestamp=entry.timestamp,
            action=entry.action,
            state=entry.state,
            completed=True,
        )
        self._save()

    def rollback(self, entry_id: str) -> None:
        """Remove an entry (used when action is rolled back)."""
        if entry_id not in self._entries:
            raise KeyError(f"No journal entry with id {entry_id!r}")
        del self._entries[entry_id]
        self._save()

    def on_startup(self) -> List[JournalEntry]:
        """Return incomplete entries found on startup (crash recovery)."""
        return [e for e in self._entries.values() if not e.completed]

    def get_entry(self, entry_id: str) -> Optional[JournalEntry]:
        """Get a specific entry by id."""
        return self._entries.get(entry_id)

    def all_entries(self) -> List[JournalEntry]:
        """Return all entries."""
        return list(self._entries.values())

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
        self._save()

    @property
    def journal_dir(self) -> str:
        return str(self._journal_dir)
