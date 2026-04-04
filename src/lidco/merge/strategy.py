"""Merge strategy advisor — recommend merge vs rebase vs squash (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Strategy(Enum):
    """Available merge strategies."""

    MERGE = "merge"
    REBASE = "rebase"
    SQUASH = "squash"


# Strategy metadata
_PROS_CONS: dict[Strategy, dict[str, list[str]]] = {
    Strategy.MERGE: {
        "pros": [
            "Preserves full branch history",
            "Non-destructive — no rewriting",
            "Easy to revert entire feature",
            "Shows merge point in graph",
        ],
        "cons": [
            "Creates extra merge commit",
            "History can look cluttered with many branches",
            "Harder to bisect through merge bubbles",
        ],
    },
    Strategy.REBASE: {
        "pros": [
            "Linear, clean history",
            "Easier to bisect and blame",
            "No merge commits",
        ],
        "cons": [
            "Rewrites commit hashes — dangerous for shared branches",
            "Can cause conflicts at each commit replay",
            "Loses merge context (when branch was integrated)",
        ],
    },
    Strategy.SQUASH: {
        "pros": [
            "Single clean commit on target branch",
            "Good for small features / fix-ups",
            "Keeps target branch tidy",
        ],
        "cons": [
            "Loses individual commit granularity",
            "Hard to attribute changes to specific commits",
            "Cannot partially revert sub-changes",
        ],
    },
}


@dataclass
class BranchInfo:
    """Lightweight branch metadata for strategy recommendation."""

    name: str
    commit_count: int = 1
    has_shared_commits: bool = False
    is_public: bool = False
    authors: list[str] = field(default_factory=list)


class MergeStrategy:
    """Advise on the best merge strategy for a branch."""

    def recommend(self, branch: BranchInfo) -> str:
        """Recommend a merge strategy based on branch characteristics.

        Returns the strategy name as a string.
        """
        if branch.is_public or branch.has_shared_commits:
            return Strategy.MERGE.value

        if branch.commit_count <= 2:
            return Strategy.SQUASH.value

        if branch.commit_count <= 10 and len(branch.authors) <= 1:
            return Strategy.REBASE.value

        return Strategy.MERGE.value

    def compare_strategies(self) -> dict[str, dict[str, list[str]]]:
        """Return a comparison of all strategies with pros and cons."""
        return {s.value: _PROS_CONS[s] for s in Strategy}

    def pros_cons(self, strategy: str) -> dict[str, list[str]]:
        """Return pros and cons for a specific strategy.

        Raises ValueError if the strategy is unknown.
        """
        try:
            key = Strategy(strategy)
        except ValueError:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Choose from: {', '.join(s.value for s in Strategy)}"
            )
        return _PROS_CONS[key]

    def is_rebase_safe(self, branch: BranchInfo) -> bool:
        """Check whether rebasing is safe for the given branch.

        Rebase is NOT safe when:
        - The branch has shared (pushed) commits
        - The branch is marked public
        - Multiple authors have contributed
        """
        if branch.is_public:
            return False
        if branch.has_shared_commits:
            return False
        if len(branch.authors) > 1:
            return False
        return True
