"""File transaction — journal-based rollback for file operations."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JournalEntry:
    """Record of a file's original state before modification."""

    path: str
    original_content: str | None  # None means file did not exist
    timestamp: float


class FileTransaction:
    """Context-manager transaction with journal-based rollback.

    Records original file contents so they can be restored on rollback.

    Usage::

        with FileTransaction() as txn:
            txn.record("foo.txt", Path("foo.txt").read_text())
            Path("foo.txt").write_text("new content")
            # on exception, txn rolls back automatically
    """

    def __init__(self, journal_path: str | None = None) -> None:
        self._journal_path = journal_path
        self._entries: list[JournalEntry] = []
        self._committed = False

    # -- recording -----------------------------------------------------------

    def record(self, path: str, original: str | None) -> None:
        """Record the original content of *path* before modification.

        Pass ``None`` if the file does not yet exist (rollback will delete it).
        """
        entry = JournalEntry(
            path=path,
            original_content=original,
            timestamp=time.time(),
        )
        self._entries.append(entry)
        self._persist_journal()

    # -- commit / rollback ---------------------------------------------------

    def commit(self) -> None:
        """Mark the transaction as committed; rollback becomes a no-op."""
        self._committed = True
        self._cleanup_journal()

    def rollback(self) -> int:
        """Restore all recorded files to their original state.

        Returns the number of files restored.
        """
        restored = 0
        for entry in reversed(self._entries):
            p = Path(entry.path)
            try:
                if entry.original_content is None:
                    if p.exists():
                        p.unlink()
                        restored += 1
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(entry.original_content, encoding="utf-8")
                    restored += 1
            except OSError:
                pass
        self._cleanup_journal()
        return restored

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> FileTransaction:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None and not self._committed:
            self.rollback()
        elif not self._committed:
            self.commit()

    # -- journal persistence -------------------------------------------------

    def _persist_journal(self) -> None:
        if self._journal_path is None:
            return
        data = [
            {
                "path": e.path,
                "original_content": e.original_content,
                "timestamp": e.timestamp,
            }
            for e in self._entries
        ]
        try:
            jp = Path(self._journal_path)
            jp.parent.mkdir(parents=True, exist_ok=True)
            jp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _cleanup_journal(self) -> None:
        if self._journal_path is None:
            return
        try:
            Path(self._journal_path).unlink(missing_ok=True)
        except OSError:
            pass

    # -- properties ----------------------------------------------------------

    @property
    def entries(self) -> tuple[JournalEntry, ...]:
        return tuple(self._entries)

    @property
    def committed(self) -> bool:
        return self._committed
