"""Append-only transcript store with JSONL persistence."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


class TranscriptError(Exception):
    """Error raised by transcript operations."""


@dataclass(frozen=True)
class TranscriptEntry:
    """Single transcript entry."""

    id: str
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: float
    tool_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TranscriptStore:
    """Append-only transcript store backed by JSONL files."""

    def __init__(self, file_path: str | Path | None = None) -> None:
        self._entries: list[TranscriptEntry] = []
        self._index: dict[str, TranscriptEntry] = {}
        self._file_path = Path(file_path) if file_path is not None else None
        if self._file_path is not None and self._file_path.exists():
            self.load(self._file_path)

    def append(
        self,
        role: str,
        content: str,
        tool_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TranscriptEntry:
        """Append a new entry to the transcript."""
        entry = TranscriptEntry(
            id=uuid.uuid4().hex[:8],
            role=role,
            content=content,
            timestamp=time.time(),
            tool_name=tool_name,
            metadata=metadata if metadata is not None else {},
        )
        self._entries.append(entry)
        self._index[entry.id] = entry
        return entry

    def get(self, entry_id: str) -> TranscriptEntry | None:
        """Retrieve an entry by ID."""
        return self._index.get(entry_id)

    def search(self, query: str, role: str | None = None) -> list[TranscriptEntry]:
        """Substring search across entries."""
        query_lower = query.lower()
        results: list[TranscriptEntry] = []
        for entry in self._entries:
            if role is not None and entry.role != role:
                continue
            if query_lower in entry.content.lower():
                results.append(entry)
        return results

    def list_entries(
        self, role: str | None = None, limit: int | None = None
    ) -> list[TranscriptEntry]:
        """List entries, optionally filtered by role and limited."""
        entries = self._entries
        if role is not None:
            entries = [e for e in entries if e.role == role]
        if limit is not None:
            entries = entries[:limit]
        return list(entries)

    def count(self) -> int:
        """Return total number of entries."""
        return len(self._entries)

    def save(self, path: str | Path | None = None) -> str:
        """Save transcript as JSONL. Returns the path used."""
        target = Path(path) if path is not None else self._file_path
        if target is None:
            raise TranscriptError("No file path specified for save.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            for entry in self._entries:
                fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return str(target)

    def load(self, path: str | Path) -> int:
        """Load entries from JSONL file. Returns count of loaded entries."""
        target = Path(path)
        if not target.exists():
            raise TranscriptError(f"File not found: {target}")
        loaded = 0
        with open(target, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                entry = TranscriptEntry(**data)
                self._entries.append(entry)
                self._index[entry.id] = entry
                loaded += 1
        return loaded

    def clear(self) -> int:
        """Clear all entries. Returns count of removed entries."""
        removed = len(self._entries)
        self._entries.clear()
        self._index.clear()
        return removed
