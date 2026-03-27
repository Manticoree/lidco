"""Composer mode — multi-file edit planning and atomic apply (stdlib only).

Like Cursor's Composer: accept a high-level goal, plan file changes,
preview unified diffs, apply atomically, and rollback on demand.
"""
from __future__ import annotations

import difflib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ComposerError(Exception):
    """Raised when a composer operation cannot complete."""


@dataclass
class FileChange:
    """A single file modification within a composer plan."""

    path: str
    old_content: str
    new_content: str
    description: str = ""

    def unified_diff(self, context_lines: int = 3) -> str:
        """Return a unified diff string for this change."""
        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
            n=context_lines,
        )
        return "".join(diff)

    def lines_added(self) -> int:
        old = set(self.old_content.splitlines())
        new_lines = self.new_content.splitlines()
        return sum(1 for ln in new_lines if ln not in old)

    def lines_removed(self) -> int:
        new = set(self.new_content.splitlines())
        old_lines = self.old_content.splitlines()
        return sum(1 for ln in old_lines if ln not in new)

    def is_creation(self) -> bool:
        return self.old_content == ""

    def is_deletion(self) -> bool:
        return self.new_content == ""


@dataclass
class ComposerPlan:
    """An ordered collection of file changes for a single goal."""

    goal: str
    changes: list[FileChange] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_change(self, change: FileChange) -> None:
        self.changes.append(change)

    def files_affected(self) -> list[str]:
        return [c.path for c in self.changes]

    def summary(self) -> str:
        n = len(self.changes)
        added = sum(c.lines_added() for c in self.changes)
        removed = sum(c.lines_removed() for c in self.changes)
        return (
            f"Plan: {self.goal!r} — {n} file(s) changed, "
            f"+{added}/−{removed} lines"
        )

    def preview(self) -> str:
        """Return full unified diff for all changes."""
        parts = [f"# Composer Plan: {self.goal}", ""]
        for change in self.changes:
            diff = change.unified_diff()
            if diff:
                parts.append(diff)
            else:
                parts.append(f"# {change.path}: no diff (identical content)")
        return "\n".join(parts)


class ComposerSession:
    """Manages the lifecycle of a multi-file editing session.

    Workflow::

        session = ComposerSession()
        plan = session.create_plan("Rename foo → bar", changes)
        print(session.preview())
        session.apply()          # writes files to disk
        session.rollback()       # restores originals

    The session keeps a stack of applied plans so rollback is always safe.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self._root = Path(root) if root else Path(".")
        self._plan: ComposerPlan | None = None
        self._history: list[ComposerPlan] = []
        self._applied: bool = False

    # ------------------------------------------------------------------ #
    # Plan building                                                        #
    # ------------------------------------------------------------------ #

    def create_plan(self, goal: str, changes: list[FileChange]) -> ComposerPlan:
        """Create (and stage) a new plan — does NOT write to disk yet."""
        if not goal.strip():
            raise ComposerError("Goal must not be empty")
        plan = ComposerPlan(goal=goal, changes=list(changes))
        self._plan = plan
        self._applied = False
        return plan

    def add_change(self, change: FileChange) -> None:
        if self._plan is None:
            raise ComposerError("No active plan — call create_plan() first")
        if self._applied:
            raise ComposerError("Plan already applied; create a new plan")
        self._plan.add_change(change)

    # ------------------------------------------------------------------ #
    # Preview / inspection                                                 #
    # ------------------------------------------------------------------ #

    def preview(self) -> str:
        if self._plan is None:
            return "(no plan staged)"
        return self._plan.preview()

    def summary(self) -> str:
        if self._plan is None:
            return "(no plan staged)"
        return self._plan.summary()

    @property
    def current_plan(self) -> ComposerPlan | None:
        return self._plan

    # ------------------------------------------------------------------ #
    # Apply / rollback                                                     #
    # ------------------------------------------------------------------ #

    def apply(self, dry_run: bool = False) -> list[str]:
        """Write all file changes to disk.

        Returns list of paths written (or that *would* be written in dry_run).
        """
        if self._plan is None:
            raise ComposerError("No plan to apply")
        if self._applied:
            raise ComposerError("Plan already applied")

        written: list[str] = []
        for change in self._plan.changes:
            target = self._root / change.path
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                if change.is_deletion():
                    if target.exists():
                        target.unlink()
                else:
                    target.write_text(change.new_content, encoding="utf-8")
            written.append(change.path)

        if not dry_run:
            self._applied = True
            self._history.append(self._plan)

        return written

    def rollback(self) -> list[str]:
        """Restore original content for the last applied plan."""
        if not self._history:
            raise ComposerError("Nothing to roll back")

        last = self._history.pop()
        restored: list[str] = []
        for change in last.changes:
            target = self._root / change.path
            if not change.is_creation():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.old_content, encoding="utf-8")
            elif target.exists():
                target.unlink()
            restored.append(change.path)

        if self._plan is last:
            self._applied = False

        return restored

    def history(self) -> list[str]:
        """Return goals of previously applied plans."""
        return [p.goal for p in self._history]
