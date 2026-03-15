"""Checkpoint-based undo for file edits — Task 283.

Before each ``file_write`` or ``file_edit`` tool call, a snapshot of the
file's previous content is saved.  ``CheckpointManager.restore(n)`` reverts
the last *n* file writes.

Usage::

    mgr = CheckpointManager()
    mgr.record("src/foo.py", old_content)  # called before each write
    mgr.restore(1)                          # undo last write
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_CHECKPOINTS = 50


@dataclass
class Checkpoint:
    """A saved file state before a write."""

    path: str
    content: Optional[str]  # None = file did not exist before write
    existed: bool


class CheckpointManager:
    """Stores per-file content snapshots and restores them on demand."""

    def __init__(self) -> None:
        self._stack: list[Checkpoint] = []

    def record(self, path: str, old_content: str | None) -> None:
        """Save a checkpoint for *path* before overwriting it.

        Args:
            path: File path being written.
            old_content: Previous file content, or ``None`` if the file
                did not exist.
        """
        cp = Checkpoint(
            path=path,
            content=old_content,
            existed=old_content is not None,
        )
        self._stack.append(cp)
        if len(self._stack) > _MAX_CHECKPOINTS:
            self._stack.pop(0)

    def restore(self, n: int = 1) -> list[str]:
        """Restore the last *n* file checkpoints.

        Returns a list of paths that were restored.
        """
        n = max(1, min(n, len(self._stack)))
        restored: list[str] = []
        for _ in range(n):
            if not self._stack:
                break
            cp = self._stack.pop()
            try:
                p = Path(cp.path)
                if cp.existed and cp.content is not None:
                    p.write_text(cp.content, encoding="utf-8")
                    restored.append(cp.path)
                elif not cp.existed and p.exists():
                    p.unlink()
                    restored.append(cp.path)
            except OSError as exc:
                logger.warning("CheckpointManager: failed to restore %s: %s", cp.path, exc)
        return restored

    def count(self) -> int:
        """Return the number of checkpoints currently stored."""
        return len(self._stack)

    def peek(self, n: int = 5) -> list[Checkpoint]:
        """Return the last *n* checkpoints (most-recent first)."""
        return list(reversed(self._stack[-n:]))

    def clear(self) -> None:
        """Discard all checkpoints."""
        self._stack.clear()
