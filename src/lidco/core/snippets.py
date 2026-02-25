"""Snippet manager — save and recall reusable code patterns."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SnippetEntry:
    key: str
    content: str
    language: str
    tags: list[str]
    created_at: float

    def matches_query(self, query: str) -> bool:
        q = query.lower()
        return (
            q in self.key.lower()
            or q in self.content.lower()
            or any(q in t.lower() for t in self.tags)
        )


class SnippetStore:
    """JSON-backed store for code snippets at `.lidco/snippets.json`."""

    def __init__(self, store_path: Path) -> None:
        self._path = store_path
        self._snippets: dict[str, SnippetEntry] = {}
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data: list[dict[str, Any]] = json.loads(self._path.read_text(encoding="utf-8"))
            for item in data:
                entry = SnippetEntry(
                    key=item["key"],
                    content=item["content"],
                    language=item.get("language", ""),
                    tags=item.get("tags", []),
                    created_at=item.get("created_at", 0.0),
                )
                self._snippets[entry.key] = entry
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self._snippets.values()]
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add(
        self,
        key: str,
        content: str,
        language: str = "",
        tags: list[str] | None = None,
    ) -> SnippetEntry:
        """Add or overwrite a snippet."""
        entry = SnippetEntry(
            key=key,
            content=content,
            language=language,
            tags=tags or [],
            created_at=time.time(),
        )
        self._snippets[key] = entry
        self._save()
        return entry

    def get(self, key: str) -> SnippetEntry | None:
        return self._snippets.get(key)

    def delete(self, key: str) -> bool:
        """Remove a snippet. Returns True if it existed."""
        if key not in self._snippets:
            return False
        del self._snippets[key]
        self._save()
        return True

    def list_all(self, tag: str | None = None) -> list[SnippetEntry]:
        entries = list(self._snippets.values())
        if tag:
            entries = [e for e in entries if tag.lower() in [t.lower() for t in e.tags]]
        return sorted(entries, key=lambda e: e.created_at, reverse=True)

    def search(self, query: str) -> list[SnippetEntry]:
        return [e for e in self._snippets.values() if e.matches_query(query)]

    def __len__(self) -> int:
        return len(self._snippets)
