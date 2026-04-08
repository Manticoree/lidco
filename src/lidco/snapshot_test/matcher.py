"""
Snapshot Matcher — compare output to snapshot, diff on mismatch, update workflow, partial matching.

Task 1678.
"""

from __future__ import annotations

import difflib
import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any

from lidco.snapshot_test.manager import SnapshotManager


@dataclass(frozen=True)
class MatchResult:
    """Result of comparing a value against a stored snapshot."""

    matched: bool
    snapshot_name: str
    diff: str = ""
    expected: str = ""
    actual: str = ""


class SnapshotMatcher:
    """Compare values to stored snapshots; produce diffs; support partial matching."""

    def __init__(self, manager: SnapshotManager, *, update: bool = False) -> None:
        self._manager = manager
        self._update = update

    @property
    def update_mode(self) -> bool:
        return self._update

    # ------------------------------------------------------------------
    # Full matching
    # ------------------------------------------------------------------

    def match(self, name: str, value: Any) -> MatchResult:
        """Match *value* against stored snapshot *name*.

        If no snapshot exists yet, it is created automatically.
        If *update* mode is on and there is a mismatch, the snapshot is updated.
        """
        serialized = self._manager.serialize(value)

        existing = self._manager.read(name)
        if existing is None:
            # First run — create snapshot
            self._manager.create(name, value)
            return MatchResult(matched=True, snapshot_name=name, expected=serialized, actual=serialized)

        expected = existing.content
        if expected == serialized:
            return MatchResult(matched=True, snapshot_name=name, expected=expected, actual=serialized)

        # Mismatch
        diff = self._make_diff(expected, serialized, name)

        if self._update:
            self._manager.update(name, value)
            return MatchResult(matched=True, snapshot_name=name, diff=diff, expected=serialized, actual=serialized)

        return MatchResult(matched=False, snapshot_name=name, diff=diff, expected=expected, actual=serialized)

    # ------------------------------------------------------------------
    # Partial matching
    # ------------------------------------------------------------------

    def match_partial(self, name: str, value: Any, *, pattern: str | None = None,
                      contains: str | None = None) -> MatchResult:
        """Match only a portion of the value or check containment.

        * *pattern*: fnmatch-style glob applied line-by-line.
        * *contains*: substring that must be present.
        """
        serialized = self._manager.serialize(value)

        existing = self._manager.read(name)
        if existing is None:
            self._manager.create(name, value)
            return MatchResult(matched=True, snapshot_name=name, expected=serialized, actual=serialized)

        expected = existing.content

        if contains is not None:
            ok = contains in serialized and contains in expected
            if not ok:
                diff = self._make_diff(expected, serialized, name)
                if self._update:
                    self._manager.update(name, value)
                    return MatchResult(matched=True, snapshot_name=name, diff=diff,
                                       expected=serialized, actual=serialized)
                return MatchResult(matched=False, snapshot_name=name, diff=diff,
                                   expected=expected, actual=serialized)
            return MatchResult(matched=True, snapshot_name=name, expected=expected, actual=serialized)

        if pattern is not None:
            exp_lines = expected.splitlines()
            act_lines = serialized.splitlines()
            filtered_exp = [l for l in exp_lines if fnmatch.fnmatch(l, pattern)]
            filtered_act = [l for l in act_lines if fnmatch.fnmatch(l, pattern)]
            if filtered_exp == filtered_act:
                return MatchResult(matched=True, snapshot_name=name, expected=expected, actual=serialized)
            diff = self._make_diff("\n".join(filtered_exp), "\n".join(filtered_act), name)
            if self._update:
                self._manager.update(name, value)
                return MatchResult(matched=True, snapshot_name=name, diff=diff,
                                   expected=serialized, actual=serialized)
            return MatchResult(matched=False, snapshot_name=name, diff=diff,
                               expected=expected, actual=serialized)

        # Fallback to full match
        return self.match(name, value)

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    @staticmethod
    def _make_diff(expected: str, actual: str, label: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                expected.splitlines(),
                actual.splitlines(),
                fromfile=f"snapshot/{label}",
                tofile="actual",
                lineterm="",
            )
        )

    def diff(self, name: str, value: Any) -> str:
        """Return a unified diff between stored snapshot and *value*."""
        serialized = self._manager.serialize(value)
        existing = self._manager.read(name)
        if existing is None:
            return ""
        return self._make_diff(existing.content, serialized, name)
