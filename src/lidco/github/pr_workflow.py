"""PRWorkflow — create and manage pull requests (simulated)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PR:
    """Pull request model."""

    id: int
    title: str
    body: str
    branch: str
    base: str
    state: str = "open"
    reviewers: list[str] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)


class PRWorkflow:
    """Simulated pull-request workflow manager."""

    def __init__(self) -> None:
        self._prs: dict[int, PR] = {}
        self._next_id: int = 1

    def create_pr(self, title: str, body: str, branch: str, base: str = "main") -> PR:
        """Create a new pull request and return it."""
        if not title:
            raise ValueError("title is required")
        if not branch:
            raise ValueError("branch is required")
        pr = PR(
            id=self._next_id,
            title=title,
            body=body,
            branch=branch,
            base=base,
        )
        self._prs[pr.id] = pr
        self._next_id += 1
        return pr

    def auto_describe(self, diff: str) -> str:
        """Generate a PR description from a diff string."""
        if not diff:
            return "No changes detected."
        lines = diff.strip().splitlines()
        additions = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        return (
            f"Auto-generated description:\n"
            f"  {additions} addition(s), {deletions} deletion(s)\n"
            f"  {len(lines)} diff line(s) total"
        )

    def request_reviewers(self, pr_id: int, reviewers: list[str]) -> bool:
        """Assign reviewers to an existing PR."""
        pr = self._prs.get(pr_id)
        if pr is None:
            return False
        pr.reviewers = list({*pr.reviewers, *reviewers})
        return True

    def list_reviews(self, pr_id: int) -> list[dict[str, Any]]:
        """Return reviews for a PR (simulated)."""
        pr = self._prs.get(pr_id)
        if pr is None:
            return []
        return [
            {"reviewer": r, "state": "approved", "body": "LGTM"}
            for r in pr.reviewers
        ]
