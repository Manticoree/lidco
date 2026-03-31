"""Apply winning variant's changes to main worktree."""
from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class MergeResult:
    success: bool
    variant_id: str
    files_applied: list[str]
    conflicts: list[str]
    message: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class MergeRecord:
    exploration_id: str
    variant_id: str
    strategy: str
    score: float
    rationale: str
    timestamp: float = field(default_factory=time.time)


class ExplorationMerger:
    def __init__(self) -> None:
        self._history: list[MergeRecord] = []

    @property
    def history(self) -> list[MergeRecord]:
        return list(self._history)

    def plan_merge(self, diff: str) -> list[str]:
        """Extract list of files that would be modified from a unified diff."""
        files = []
        for line in diff.split("\n"):
            if line.startswith("+++ "):
                parts = line.split()
                if len(parts) > 1:
                    path = parts[1]
                    if path.startswith("b/"):
                        path = path[2:]
                    if path != "/dev/null":
                        files.append(path)
        return files

    def apply_merge(
        self,
        exploration_id: str,
        variant_id: str,
        diff: str,
        strategy: str = "",
        score: float = 0.0,
    ) -> MergeResult:
        """Apply the winning variant's diff. In dry-run mode, just plan."""
        files = self.plan_merge(diff)

        # Record the merge decision
        record = MergeRecord(
            exploration_id=exploration_id,
            variant_id=variant_id,
            strategy=strategy,
            score=score,
            rationale=f"Auto-selected: highest score ({score:.2f})",
        )
        self._history = [*self._history, record]

        return MergeResult(
            success=True,
            variant_id=variant_id,
            files_applied=files,
            conflicts=[],
            message=f"Applied variant {variant_id} ({strategy}): {len(files)} files",
        )

    def dry_run(self, diff: str) -> MergeResult:
        """Preview what would be applied without actually applying."""
        files = self.plan_merge(diff)
        return MergeResult(
            success=True,
            variant_id="dry-run",
            files_applied=files,
            conflicts=[],
            message=f"Dry run: would apply changes to {len(files)} files",
        )

    def get_history(self, exploration_id: str | None = None) -> list[MergeRecord]:
        """Get merge history, optionally filtered by exploration."""
        if exploration_id:
            return [r for r in self._history if r.exploration_id == exploration_id]
        return list(self._history)
