"""AutoCheckpoint -- periodic checkpoint save/restore for session resilience (stdlib only)."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Checkpoint:
    """A single checkpoint snapshot."""

    id: str
    label: str
    timestamp: float
    data: dict
    size_bytes: int


class AutoCheckpoint:
    """Manage a bounded list of in-memory checkpoints with interval gating."""

    def __init__(
        self,
        max_checkpoints: int = 10,
        interval_seconds: float = 60.0,
    ) -> None:
        self._max_checkpoints = max_checkpoints
        self._interval_seconds = interval_seconds
        self._checkpoints: list[Checkpoint] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, label: str, data: dict) -> Checkpoint:
        """Create and store a new checkpoint, returning it."""
        serialized = json.dumps(data)
        cp = Checkpoint(
            id=uuid.uuid4().hex,
            label=label,
            timestamp=time.time(),
            data=data,
            size_bytes=len(serialized.encode("utf-8")),
        )
        self._checkpoints.append(cp)
        self.cleanup()
        return cp

    def should_save(self, last_save_time: float) -> bool:
        """Return *True* if at least *interval_seconds* elapsed since *last_save_time*."""
        return (time.time() - last_save_time) >= self._interval_seconds

    def latest(self) -> Optional[Checkpoint]:
        """Return the most recent checkpoint, or *None*."""
        if not self._checkpoints:
            return None
        return self._checkpoints[-1]

    def list_checkpoints(self) -> list[Checkpoint]:
        """Return all stored checkpoints, newest first."""
        return list(reversed(self._checkpoints))

    def restore(self, checkpoint_id: str) -> Optional[dict]:
        """Return checkpoint data for *checkpoint_id*, or *None*."""
        for cp in self._checkpoints:
            if cp.id == checkpoint_id:
                return cp.data
        return None

    def cleanup(self) -> None:
        """Remove oldest checkpoints when count exceeds *max_checkpoints*."""
        while len(self._checkpoints) > self._max_checkpoints:
            self._checkpoints.pop(0)

    def clear(self) -> None:
        """Remove all checkpoints."""
        self._checkpoints.clear()
