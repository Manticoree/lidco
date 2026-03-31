"""Session checkpoint manager — Q160."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class Checkpoint:
    """A saved snapshot of session state."""

    checkpoint_id: str
    timestamp: float
    file_snapshots: dict[str, str]  # path -> content
    conversation_length: int
    label: str = ""


@dataclass
class RewindResult:
    """Result of a rewind operation."""

    restored_files: list[str]
    conversation_truncate_to: int | None
    success: bool


class CheckpointManager:
    """Manage session checkpoints with create / list / rewind / fork."""

    def __init__(
        self,
        max_checkpoints: int = 50,
        read_fn: Callable[[str], str] | None = None,
        write_fn: Callable[[str, str], None] | None = None,
    ) -> None:
        self._max_checkpoints = max_checkpoints
        self._read_fn = read_fn
        self._write_fn = write_fn
        self._checkpoints: list[Checkpoint] = []

    # -- create -------------------------------------------------------------

    def create(
        self,
        files: dict[str, str],
        conversation_length: int,
        label: str = "",
    ) -> Checkpoint:
        """Create a new checkpoint from the given file contents."""
        cp = Checkpoint(
            checkpoint_id=uuid.uuid4().hex[:12],
            timestamp=time.time(),
            file_snapshots=dict(files),
            conversation_length=conversation_length,
            label=label,
        )
        self._checkpoints.append(cp)
        # Evict oldest when over the limit
        while len(self._checkpoints) > self._max_checkpoints:
            self._checkpoints.pop(0)
        return cp

    # -- query --------------------------------------------------------------

    def list(self) -> list[Checkpoint]:
        """Return all checkpoints (oldest first)."""
        return list(self._checkpoints)

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        """Lookup a checkpoint by id."""
        for cp in self._checkpoints:
            if cp.checkpoint_id == checkpoint_id:
                return cp
        return None

    # -- rewind -------------------------------------------------------------

    def rewind_to(
        self,
        checkpoint_id: str,
        mode: str = "both",
    ) -> RewindResult:
        """Rewind session state to a checkpoint.

        *mode* controls what gets restored:
          - ``"code"``: restore files only
          - ``"chat"``: return conversation_length to truncate to
          - ``"both"``: both of the above
        """
        cp = self.get(checkpoint_id)
        if cp is None:
            return RewindResult(restored_files=[], conversation_truncate_to=None, success=False)

        restored: list[str] = []
        truncate_to: int | None = None

        if mode in ("code", "both"):
            if self._write_fn is not None:
                for path, content in cp.file_snapshots.items():
                    self._write_fn(path, content)
                    restored.append(path)
            else:
                restored = list(cp.file_snapshots.keys())

        if mode in ("chat", "both"):
            truncate_to = cp.conversation_length

        return RewindResult(
            restored_files=restored,
            conversation_truncate_to=truncate_to,
            success=True,
        )

    # -- fork ---------------------------------------------------------------

    def fork(self, checkpoint_id: str) -> Checkpoint:
        """Create a new checkpoint that is a copy of an existing one.

        Raises ``KeyError`` if *checkpoint_id* is not found.
        """
        cp = self.get(checkpoint_id)
        if cp is None:
            raise KeyError(f"Checkpoint '{checkpoint_id}' not found")
        return self.create(
            files=dict(cp.file_snapshots),
            conversation_length=cp.conversation_length,
            label=f"fork of {cp.label or cp.checkpoint_id}",
        )

    # -- housekeeping -------------------------------------------------------

    def clear(self) -> None:
        """Remove all checkpoints."""
        self._checkpoints.clear()

    def __len__(self) -> int:
        return len(self._checkpoints)
