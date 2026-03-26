"""
Undo/Redo Manager — track file changes and allow reverting agent edits.

Architecture:
- UndoManager maintains a stack of checkpoints (named snapshots of file content).
- Calling checkpoint("label") saves the current content of watched files.
- undo() restores files to the previous checkpoint, advancing the redo stack.
- redo() replays undone checkpoints.
- Works file-by-file or across a set of files.

Stdlib only — no external deps.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileSnapshot:
    """A snapshot of a single file's content at a point in time."""
    path: str
    content: str          # file text at snapshot time
    existed: bool         # False if file did not exist yet
    timestamp: float = field(default_factory=time.time)

    @property
    def size(self) -> int:
        return len(self.content.encode("utf-8"))


@dataclass
class Checkpoint:
    """A named collection of file snapshots taken at one moment."""
    label: str
    snapshots: dict[str, FileSnapshot]   # path → snapshot
    timestamp: float = field(default_factory=time.time)

    @property
    def file_count(self) -> int:
        return len(self.snapshots)

    def summary(self) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        return f"[{ts}] {self.label} ({self.file_count} file(s))"


@dataclass
class UndoResult:
    """Result of an undo or redo operation."""
    success: bool
    checkpoint: Checkpoint | None
    restored_files: list[str]
    error: str = ""


# ---------------------------------------------------------------------------
# UndoManager
# ---------------------------------------------------------------------------

class UndoManager:
    """
    Track file edits and support undo/redo across checkpoints.

    Parameters
    ----------
    max_checkpoints : int
        Maximum number of undo checkpoints to keep. Oldest are discarded.
    watched_files : list[str] | None
        Files to include in every checkpoint. Can be extended later.
    """

    def __init__(
        self,
        max_checkpoints: int = 50,
        watched_files: list[str] | None = None,
    ) -> None:
        self._max = max_checkpoints
        self._watched: set[str] = set(watched_files or [])
        self._undo_stack: list[Checkpoint] = []
        self._redo_stack: list[Checkpoint] = []

    # ------------------------------------------------------------------
    # File watching
    # ------------------------------------------------------------------

    def watch(self, *paths: str) -> None:
        """Add files to the watch list."""
        self._watched.update(paths)

    def unwatch(self, *paths: str) -> None:
        """Remove files from the watch list."""
        self._watched.difference_update(paths)

    @property
    def watched_files(self) -> list[str]:
        return sorted(self._watched)

    # ------------------------------------------------------------------
    # Checkpoint creation
    # ------------------------------------------------------------------

    def checkpoint(
        self,
        label: str = "checkpoint",
        extra_files: list[str] | None = None,
    ) -> Checkpoint:
        """
        Save a snapshot of all watched (and extra) files.

        Parameters
        ----------
        label : str
            Human-readable label for this checkpoint.
        extra_files : list[str] | None
            Additional files to snapshot beyond the watch list.
        """
        paths = set(self._watched)
        if extra_files:
            paths.update(extra_files)

        snapshots: dict[str, FileSnapshot] = {}
        for p in sorted(paths):
            path_obj = Path(p)
            if path_obj.exists():
                try:
                    content = path_obj.read_text(encoding="utf-8", errors="replace")
                    snapshots[p] = FileSnapshot(path=p, content=content, existed=True)
                except OSError:
                    snapshots[p] = FileSnapshot(path=p, content="", existed=False)
            else:
                snapshots[p] = FileSnapshot(path=p, content="", existed=False)

        cp = Checkpoint(label=label, snapshots=snapshots)
        self._undo_stack.append(cp)
        self._redo_stack.clear()   # new checkpoint invalidates redo

        # Enforce max
        if len(self._undo_stack) > self._max:
            self._undo_stack = self._undo_stack[-self._max:]

        return cp

    def checkpoint_file(self, path: str, label: str = "checkpoint") -> Checkpoint:
        """Snapshot a single file (convenience method)."""
        return self.checkpoint(label=label, extra_files=[path])

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def undo(self) -> UndoResult:
        """
        Restore files to the most recent checkpoint.

        The current checkpoint is moved to the redo stack so it can be
        replayed with redo().
        """
        if len(self._undo_stack) < 2:
            # Need at least 2: the "before" state and the "after" state
            if not self._undo_stack:
                return UndoResult(
                    success=False,
                    checkpoint=None,
                    restored_files=[],
                    error="No checkpoints available",
                )
            return UndoResult(
                success=False,
                checkpoint=self._undo_stack[0],
                restored_files=[],
                error="Already at oldest checkpoint",
            )

        # Current state (to push onto redo)
        current = self._undo_stack.pop()
        self._redo_stack.append(current)

        # Target state (restore)
        target = self._undo_stack[-1]
        restored = self._restore_checkpoint(target)
        return UndoResult(success=True, checkpoint=target, restored_files=restored)

    def redo(self) -> UndoResult:
        """
        Re-apply the most recently undone checkpoint.
        """
        if not self._redo_stack:
            return UndoResult(
                success=False,
                checkpoint=None,
                restored_files=[],
                error="Nothing to redo",
            )

        target = self._redo_stack.pop()
        self._undo_stack.append(target)
        restored = self._restore_checkpoint(target)
        return UndoResult(success=True, checkpoint=target, restored_files=restored)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def list_history(self) -> list[str]:
        """Return summary strings for all undo checkpoints (oldest first)."""
        return [cp.summary() for cp in self._undo_stack]

    def list_redo(self) -> list[str]:
        """Return summary strings for redo stack (most recent first)."""
        return [cp.summary() for cp in reversed(self._redo_stack)]

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) >= 2

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self) -> None:
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _restore_checkpoint(self, cp: Checkpoint) -> list[str]:
        """Write snapshot content back to disk. Returns list of restored paths."""
        restored: list[str] = []
        for path, snap in cp.snapshots.items():
            p = Path(path)
            try:
                if snap.existed:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(snap.content, encoding="utf-8")
                    restored.append(path)
                else:
                    # File didn't exist at checkpoint time → delete if present now
                    if p.exists():
                        p.unlink()
                        restored.append(path)
            except OSError:
                pass  # Best-effort restore
        return restored
