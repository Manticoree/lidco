"""File index with content hashing — Q127."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class IndexEntry:
    path: str
    size: int
    mtime: float
    content_hash: str  # sha256 hex of content


def _default_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class FileIndex:
    """Index files by path with hash-based change detection."""

    def __init__(self, hash_fn: Callable[[str], str] = None) -> None:
        self._hash_fn = hash_fn or _default_hash
        self._entries: dict[str, IndexEntry] = {}

    def index_file(self, path: str, content: str, mtime: float = 0.0) -> IndexEntry:
        entry = IndexEntry(
            path=path,
            size=len(content.encode("utf-8")),
            mtime=mtime,
            content_hash=self._hash_fn(content),
        )
        self._entries[path] = entry
        return entry

    def get(self, path: str) -> Optional[IndexEntry]:
        return self._entries.get(path)

    def has_changed(self, path: str, content: str) -> bool:
        """Return True if the file's hash differs from the indexed hash."""
        entry = self._entries.get(path)
        if entry is None:
            return True
        return entry.content_hash != self._hash_fn(content)

    def remove(self, path: str) -> bool:
        if path in self._entries:
            del self._entries[path]
            return True
        return False

    def list_paths(self) -> list[str]:
        return list(self._entries.keys())

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
