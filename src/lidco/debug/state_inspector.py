"""Q133: State snapshot and diff inspector."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StateSnapshot:
    id: str
    label: str
    data: dict
    timestamp: float


class StateInspector:
    """Capture and compare state snapshots."""

    def __init__(self) -> None:
        self._snapshots: list[StateSnapshot] = []
        self._index: dict[str, StateSnapshot] = {}

    def capture(self, data: dict, label: str = "") -> StateSnapshot:
        snap = StateSnapshot(
            id=str(uuid.uuid4()),
            label=label,
            data=dict(data),
            timestamp=time.time(),
        )
        self._snapshots.append(snap)
        self._index[snap.id] = snap
        return snap

    def diff(self, snap_a: StateSnapshot, snap_b: StateSnapshot) -> dict:
        """Compute added/removed/changed keys between two snapshots."""
        a, b = snap_a.data, snap_b.data
        added = {k: v for k, v in b.items() if k not in a}
        removed = {k: v for k, v in a.items() if k not in b}
        changed = {
            k: (a[k], b[k])
            for k in a
            if k in b and a[k] != b[k]
        }
        return {"added": added, "removed": removed, "changed": changed}

    def list_snapshots(self) -> list[StateSnapshot]:
        return list(self._snapshots)

    def get(self, id: str) -> Optional[StateSnapshot]:
        return self._index.get(id)

    def clear(self) -> None:
        self._snapshots.clear()
        self._index.clear()

    def replay(self, snapshots: list[StateSnapshot]) -> list[dict]:
        """Return list of diffs between consecutive snapshots."""
        diffs: list[dict] = []
        for i in range(1, len(snapshots)):
            diffs.append(self.diff(snapshots[i - 1], snapshots[i]))
        return diffs
