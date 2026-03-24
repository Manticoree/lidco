"""File-level checkpoint management for flow steps."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Checkpoint:
    id: str
    step_index: int
    step_name: str
    timestamp: float
    files: dict[str, str]  # path -> content snapshot


class FlowCheckpointManager:
    """Saves and restores file-level checkpoints before each flow step."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._checkpoints: dict[str, Checkpoint] = {}

    @property
    def checkpoints(self) -> dict[str, Checkpoint]:
        return dict(self._checkpoints)

    def save(self, step_index: int, step_name: str, files: list[str]) -> Checkpoint:
        """Snapshot the given file paths and store a checkpoint."""
        snapshot: dict[str, str] = {}
        for rel_path in files:
            abs_path = self._project_dir / rel_path
            if abs_path.exists():
                snapshot[rel_path] = abs_path.read_text(encoding="utf-8", errors="replace")
            else:
                snapshot[rel_path] = ""

        cp_id = f"step_{step_index}_{int(time.time() * 1000)}"
        cp = Checkpoint(
            id=cp_id,
            step_index=step_index,
            step_name=step_name,
            timestamp=time.time(),
            files=snapshot,
        )
        self._checkpoints[cp_id] = cp
        return cp

    def rollback(self, checkpoint_id: str) -> bool:
        """Restore files to state at named checkpoint. Returns True on success."""
        cp = self._checkpoints.get(checkpoint_id)
        if cp is None:
            return False
        for rel_path, content in cp.files.items():
            abs_path = self._project_dir / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content, encoding="utf-8")
        return True

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        return self._checkpoints.get(checkpoint_id)

    def list(self) -> list[Checkpoint]:
        return sorted(self._checkpoints.values(), key=lambda c: c.step_index)
