"""SessionCheckpointStore -- save/restore/diff conversation checkpoints."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CheckpointNotFoundError(Exception):
    """Raised when a checkpoint id is not found."""


@dataclass
class SessionCheckpoint:
    """A snapshot of conversation state."""

    id: str
    label: str
    created_at: str  # ISO timestamp
    messages: list[dict] = field(default_factory=list)
    file_refs: list[str] = field(default_factory=list)
    memory_snapshot: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "created_at": self.created_at,
            "messages": list(self.messages),
            "file_refs": list(self.file_refs),
            "memory_snapshot": list(self.memory_snapshot),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SessionCheckpoint:
        return cls(
            id=d["id"],
            label=d["label"],
            created_at=d["created_at"],
            messages=d.get("messages", []),
            file_refs=d.get("file_refs", []),
            memory_snapshot=d.get("memory_snapshot", []),
        )


@dataclass
class CheckpointDiff:
    """Difference between two checkpoints."""

    messages_added: int
    messages_removed: int
    files_changed: list[str] = field(default_factory=list)


class SessionCheckpointStore:
    """JSON-persisted checkpoint store for conversation snapshots."""

    def __init__(self, storage_path: str = ".lidco/checkpoints.json") -> None:
        self._path = Path(storage_path)
        self._checkpoints: dict[str, SessionCheckpoint] = {}
        self._load()

    def save(
        self,
        label: str,
        messages: list[dict],
        file_refs: list[str] | None = None,
        memory_snapshot: list[dict] | None = None,
    ) -> str:
        """Save a checkpoint and return its id."""
        cp_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        checkpoint = SessionCheckpoint(
            id=cp_id,
            label=label,
            created_at=now,
            messages=list(messages) if messages else [],
            file_refs=list(file_refs) if file_refs else [],
            memory_snapshot=list(memory_snapshot) if memory_snapshot else [],
        )
        self._checkpoints[cp_id] = checkpoint
        self._save()
        return cp_id

    def list(self) -> list[SessionCheckpoint]:
        """Return all checkpoints ordered by creation time."""
        items = sorted(self._checkpoints.values(), key=lambda c: c.created_at)
        return list(items)

    def restore(self, checkpoint_id: str) -> SessionCheckpoint:
        """Restore a checkpoint by id."""
        if checkpoint_id not in self._checkpoints:
            raise CheckpointNotFoundError(f"Checkpoint not found: {checkpoint_id}")
        return self._checkpoints[checkpoint_id]

    def diff(self, id1: str, id2: str) -> CheckpointDiff:
        """Compare two checkpoints."""
        cp1 = self.restore(id1)
        cp2 = self.restore(id2)

        msgs1 = {json.dumps(m, sort_keys=True) for m in cp1.messages}
        msgs2 = {json.dumps(m, sort_keys=True) for m in cp2.messages}

        added = len(msgs2 - msgs1)
        removed = len(msgs1 - msgs2)

        files1 = set(cp1.file_refs)
        files2 = set(cp2.file_refs)
        files_changed = sorted(files1.symmetric_difference(files2))

        return CheckpointDiff(
            messages_added=added,
            messages_removed=removed,
            files_changed=files_changed,
        )

    def delete(self, checkpoint_id: str) -> None:
        """Delete a checkpoint."""
        if checkpoint_id not in self._checkpoints:
            raise CheckpointNotFoundError(f"Checkpoint not found: {checkpoint_id}")
        del self._checkpoints[checkpoint_id]
        self._save()

    def count(self) -> int:
        """Return number of stored checkpoints."""
        return len(self._checkpoints)

    def get(self, checkpoint_id: str) -> SessionCheckpoint | None:
        """Get a checkpoint by id, or None."""
        return self._checkpoints.get(checkpoint_id)

    def clear(self) -> int:
        """Remove all checkpoints. Returns count removed."""
        count = len(self._checkpoints)
        self._checkpoints.clear()
        self._save()
        return count

    def _load(self) -> None:
        """Load checkpoints from JSON file."""
        if not self._path.exists():
            self._checkpoints = {}
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._checkpoints = {}
            for item in data:
                cp = SessionCheckpoint.from_dict(item)
                self._checkpoints[cp.id] = cp
        except (json.JSONDecodeError, KeyError, TypeError):
            self._checkpoints = {}

    def _save(self) -> None:
        """Persist checkpoints to JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        items = [cp.to_dict() for cp in self._checkpoints.values()]
        self._path.write_text(json.dumps(items, indent=2), encoding="utf-8")
