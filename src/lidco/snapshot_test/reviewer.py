"""
Snapshot Reviewer — interactive review of snapshot changes; accept/reject; bulk update; history.

Task 1679.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lidco.snapshot_test.manager import SnapshotManager
from lidco.snapshot_test.matcher import SnapshotMatcher


@dataclass(frozen=True)
class ReviewItem:
    """A pending snapshot change awaiting review."""

    name: str
    old_content: str
    new_content: str
    diff: str
    timestamp: float = 0.0


@dataclass(frozen=True)
class ReviewDecision:
    """A recorded accept/reject decision."""

    name: str
    accepted: bool
    reviewed_at: float
    reviewer: str = ""


class SnapshotReviewer:
    """Collect snapshot changes, present for review, accept/reject, track history."""

    HISTORY_FILE = "review_history.json"

    def __init__(self, manager: SnapshotManager) -> None:
        self._manager = manager
        self._pending: dict[str, ReviewItem] = {}
        self._history: list[ReviewDecision] = []
        self._load_history()

    # ------------------------------------------------------------------
    # Pending changes
    # ------------------------------------------------------------------

    def add_pending(self, name: str, new_value: Any) -> ReviewItem:
        """Register a snapshot change for review."""
        serialized = self._manager.serialize(new_value)
        existing = self._manager.read(name)
        old = existing.content if existing else ""

        matcher = SnapshotMatcher(self._manager)
        diff = matcher.diff(name, new_value)

        item = ReviewItem(
            name=name,
            old_content=old,
            new_content=serialized,
            diff=diff,
            timestamp=time.time(),
        )
        self._pending[name] = item
        return item

    def list_pending(self) -> list[ReviewItem]:
        """Return all pending review items sorted by name."""
        return sorted(self._pending.values(), key=lambda r: r.name)

    def pending_count(self) -> int:
        return len(self._pending)

    # ------------------------------------------------------------------
    # Accept / Reject
    # ------------------------------------------------------------------

    def accept(self, name: str, *, reviewer: str = "") -> ReviewDecision | None:
        """Accept a pending change — update the snapshot."""
        item = self._pending.pop(name, None)
        if item is None:
            return None
        self._manager.update(name, item.new_content)
        decision = ReviewDecision(name=name, accepted=True, reviewed_at=time.time(), reviewer=reviewer)
        self._history.append(decision)
        self._save_history()
        return decision

    def reject(self, name: str, *, reviewer: str = "") -> ReviewDecision | None:
        """Reject a pending change — leave the snapshot as-is."""
        item = self._pending.pop(name, None)
        if item is None:
            return None
        decision = ReviewDecision(name=name, accepted=False, reviewed_at=time.time(), reviewer=reviewer)
        self._history.append(decision)
        self._save_history()
        return decision

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def accept_all(self, *, reviewer: str = "") -> list[ReviewDecision]:
        """Accept every pending change."""
        decisions: list[ReviewDecision] = []
        for name in list(self._pending):
            d = self.accept(name, reviewer=reviewer)
            if d is not None:
                decisions.append(d)
        return decisions

    def reject_all(self, *, reviewer: str = "") -> list[ReviewDecision]:
        """Reject every pending change."""
        decisions: list[ReviewDecision] = []
        for name in list(self._pending):
            d = self.reject(name, reviewer=reviewer)
            if d is not None:
                decisions.append(d)
        return decisions

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, *, name: str | None = None) -> list[ReviewDecision]:
        """Return review history, optionally filtered by snapshot name."""
        if name is None:
            return list(self._history)
        return [d for d in self._history if d.name == name]

    def clear_history(self) -> int:
        """Clear history. Returns number of entries removed."""
        count = len(self._history)
        self._history.clear()
        self._save_history()
        return count

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _history_path(self) -> Path:
        return self._manager.snapshot_dir / self.HISTORY_FILE

    def _load_history(self) -> None:
        p = self._history_path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                self._history = [
                    ReviewDecision(
                        name=d["name"],
                        accepted=d["accepted"],
                        reviewed_at=d["reviewed_at"],
                        reviewer=d.get("reviewer", ""),
                    )
                    for d in data
                ]
            except (json.JSONDecodeError, KeyError):
                self._history = []

    def _save_history(self) -> None:
        p = self._history_path()
        p.write_text(
            json.dumps(
                [
                    {
                        "name": d.name,
                        "accepted": d.accepted,
                        "reviewed_at": d.reviewed_at,
                        "reviewer": d.reviewer,
                    }
                    for d in self._history
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
