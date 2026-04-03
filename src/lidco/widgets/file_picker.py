"""FilePicker widget — file selection, fuzzy search, bookmarks, recent."""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass

from lidco.widgets.framework import Widget


@dataclass(frozen=True)
class FileEntry:
    """Represents a file or directory entry."""

    path: str
    name: str
    is_dir: bool = False
    size: int = 0


class FilePicker(Widget):
    """Interactive file picker with search, bookmarks, and recent files."""

    def __init__(self, root: str = ".") -> None:
        super().__init__(id="file-picker", title="File Picker")
        self.root = root
        self._entries: dict[str, FileEntry] = {}
        self._bookmarks: list[str] = []
        self._recent: list[str] = []

    def add_entry(self, path: str, is_dir: bool = False, size: int = 0) -> FileEntry:
        """Add a file entry (primarily for testing)."""
        name = os.path.basename(path) or path
        entry = FileEntry(path=path, name=name, is_dir=is_dir, size=size)
        self._entries[path] = entry
        return entry

    def list_files(self, directory: str | None = None) -> list[FileEntry]:
        """List entries, optionally filtered by directory prefix."""
        if directory is None:
            return list(self._entries.values())
        prefix = directory.rstrip("/") + "/"
        return [e for e in self._entries.values() if e.path.startswith(prefix) or e.path == directory]

    def search(self, query: str) -> list[FileEntry]:
        """Fuzzy-match entries by name or path."""
        if not query:
            return list(self._entries.values())
        q_lower = query.lower()
        results: list[FileEntry] = []
        for entry in self._entries.values():
            if q_lower in entry.name.lower() or q_lower in entry.path.lower():
                results.append(entry)
            elif fnmatch.fnmatch(entry.name.lower(), f"*{q_lower}*"):
                results.append(entry)
        return results

    def select(self, path: str) -> FileEntry | None:
        """Select a file entry by path, adding to recent."""
        entry = self._entries.get(path)
        if entry is not None:
            self.add_recent(path)
        return entry

    def add_bookmark(self, path: str) -> None:
        if path not in self._bookmarks:
            self._bookmarks.append(path)

    def remove_bookmark(self, path: str) -> bool:
        if path in self._bookmarks:
            self._bookmarks.remove(path)
            return True
        return False

    def bookmarks(self) -> list[str]:
        return list(self._bookmarks)

    def add_recent(self, path: str) -> None:
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)

    def recent(self, limit: int = 10) -> list[str]:
        return self._recent[:limit]

    def render(self) -> str:
        count = len(self._entries)
        bm = len(self._bookmarks)
        return f"[FilePicker] {count} files, {bm} bookmarks, root={self.root}"
