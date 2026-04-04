"""PRReviewerMatcher — suggest reviewers based on file ownership and expertise (stdlib only)."""
from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Reviewer:
    """A reviewer suggestion."""
    user: str
    reason: str
    score: float = 1.0


class PRReviewerMatcher:
    """Match reviewers to PR files using ownership rules and activity tracking.

    All state is kept in-memory; no external deps.
    """

    def __init__(self) -> None:
        self._owners: list[tuple[str, str]] = []  # (glob_pattern, user)
        self._codeowners: list[tuple[str, str]] = []  # (glob_pattern, team)
        self._activity: dict[str, list[float]] = {}  # user -> list of timestamps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_owner(self, path_pattern: str, user: str) -> None:
        """Register *user* as owner for files matching *path_pattern* (glob)."""
        self._owners = [*self._owners, (path_pattern, user)]

    def add_codeowner(self, pattern: str, team: str) -> None:
        """Register *team* as a CODEOWNERS entry for *pattern*."""
        self._codeowners = [*self._codeowners, (pattern, team)]

    def suggest(self, files: list[str]) -> list[Reviewer]:
        """Return a deduplicated list of Reviewer suggestions for the given files."""
        seen: set[str] = set()
        results: list[Reviewer] = []
        for f in files:
            for pattern, user in self._owners:
                if fnmatch.fnmatch(f, pattern) and user not in seen:
                    seen.add(user)
                    results.append(Reviewer(user=user, reason=f"owns {pattern}", score=1.0))
            for pattern, team in self._codeowners:
                if fnmatch.fnmatch(f, pattern) and team not in seen:
                    seen.add(team)
                    results.append(Reviewer(user=team, reason=f"codeowner {pattern}", score=0.8))
        return results

    def match_expertise(self, file: str) -> list[Reviewer]:
        """Return reviewers whose ownership patterns match a single file."""
        return self.suggest([file])

    def record_activity(self, user: str) -> None:
        """Record a review activity timestamp for *user*."""
        self._activity = {
            **self._activity,
            user: [*self._activity.get(user, []), time.time()],
        }

    def recent_activity(self, user: str) -> int:
        """Return the number of recorded activity entries for *user*."""
        return len(self._activity.get(user, []))
