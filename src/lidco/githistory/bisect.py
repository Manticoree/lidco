"""BisectAssistant — binary-search bisect helper for finding bad commits."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BisectStep:
    """Record of one bisect test."""

    hash: str
    passed: bool


class BisectAssistant:
    """Interactive binary-search bisect over a linear commit list.

    Usage:
        ba = BisectAssistant()
        ba.start(good="abc", bad="xyz", commits=["abc", ..., "xyz"])
        while not ba.found():
            result = ba.test_commit(ba.current(), passed=run_test(ba.current()))
            # result is either next hash or "found"
    """

    def __init__(self) -> None:
        self._commits: list[str] = []
        self._good_idx: int = 0
        self._bad_idx: int = 0
        self._history: list[BisectStep] = []
        self._found: str | None = None
        self._started: bool = False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def start(self, good: str, bad: str, commits: list[str] | None = None) -> None:
        """Begin a bisect session.

        *commits* is the ordered list of hashes from oldest to newest.
        *good* and *bad* must both appear in *commits*.
        """
        if commits is None or len(commits) < 2:
            raise ValueError("commits list must have at least 2 entries")
        if good not in commits:
            raise ValueError(f"good commit {good!r} not in commits list")
        if bad not in commits:
            raise ValueError(f"bad commit {bad!r} not in commits list")

        self._commits = list(commits)
        self._good_idx = self._commits.index(good)
        self._bad_idx = self._commits.index(bad)
        if self._good_idx >= self._bad_idx:
            raise ValueError("good commit must come before bad commit in the list")
        self._history = []
        self._found = None
        self._started = True

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def current(self) -> str:
        """Return the current commit to test."""
        self._ensure_started()
        if self._found is not None:
            return self._found
        mid = (self._good_idx + self._bad_idx) // 2
        return self._commits[mid]

    def test_commit(self, hash: str, passed: bool) -> str:
        """Record a test result and return the next commit or 'found'."""
        self._ensure_started()
        if self._found is not None:
            return "found"

        self._history.append(BisectStep(hash=hash, passed=passed))

        mid = (self._good_idx + self._bad_idx) // 2

        if passed:
            self._good_idx = mid
        else:
            self._bad_idx = mid

        if self._bad_idx - self._good_idx <= 1:
            self._found = self._commits[self._bad_idx]
            return "found"

        return self.current()

    def history(self) -> list[BisectStep]:
        """Return the list of all bisect steps so far."""
        return list(self._history)

    def found(self) -> str | None:
        """Return the found bad commit, or None if still searching."""
        return self._found

    def steps_remaining(self) -> int:
        """Estimate how many more steps remain."""
        if self._found is not None:
            return 0
        remaining = self._bad_idx - self._good_idx
        if remaining <= 1:
            return 0
        return max(1, math.ceil(math.log2(remaining)))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("bisect not started; call start() first")
