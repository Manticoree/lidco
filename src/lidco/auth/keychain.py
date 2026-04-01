"""Simulated keychain storage (no actual OS keychain)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KeychainEntry:
    """A single keychain entry."""

    service: str
    key: str
    value: str
    created_at: float


class KeychainStorage:
    """In-memory keychain with optional JSON persistence."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._entries: dict[tuple[str, str], KeychainEntry] = {}
        self._storage_path = Path(storage_path) if storage_path else None

    # -- CRUD ----------------------------------------------------------

    def set(self, service: str, key: str, value: str) -> None:
        """Store a value under *(service, key)*."""
        self._entries[(service, key)] = KeychainEntry(
            service=service,
            key=key,
            value=value,
            created_at=time.time(),
        )

    def get(self, service: str, key: str) -> str | None:
        """Retrieve the value for *(service, key)*, or ``None``."""
        entry = self._entries.get((service, key))
        return entry.value if entry is not None else None

    def delete(self, service: str, key: str) -> bool:
        """Delete an entry. Return whether it existed."""
        return self._entries.pop((service, key), None) is not None

    def has(self, service: str, key: str) -> bool:
        """Return True if *(service, key)* exists."""
        return (service, key) in self._entries

    def list_entries(self, service: str | None = None) -> list[KeychainEntry]:
        """List entries, optionally filtered by *service*."""
        entries = list(self._entries.values())
        if service is not None:
            entries = [e for e in entries if e.service == service]
        return sorted(entries, key=lambda e: (e.service, e.key))

    # -- Persistence ---------------------------------------------------

    def save(self, path: str | Path | None = None) -> str:
        """Persist entries to JSON. Return the file path used."""
        target = Path(path) if path else self._storage_path
        if target is None:
            raise ValueError("No storage path configured")
        data: list[dict[str, Any]] = [asdict(e) for e in self._entries.values()]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return str(target)

    def load(self, path: str | Path) -> int:
        """Load entries from a JSON file. Return the count loaded."""
        target = Path(path)
        raw: list[dict[str, Any]] = json.loads(target.read_text(encoding="utf-8"))
        count = 0
        for item in raw:
            entry = KeychainEntry(
                service=item["service"],
                key=item["key"],
                value=item["value"],
                created_at=item["created_at"],
            )
            self._entries[(entry.service, entry.key)] = entry
            count += 1
        return count

    def clear(self) -> int:
        """Remove all entries. Return the count removed."""
        count = len(self._entries)
        self._entries.clear()
        return count
