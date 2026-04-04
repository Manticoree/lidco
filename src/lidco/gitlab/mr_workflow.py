"""
Merge-request workflow helpers for GitLab.

Create MRs, auto-describe from diffs, assign reviewers, approve, list discussions.
All operations are simulated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MR:
    """Represents a GitLab merge request."""

    id: int
    title: str
    description: str
    source_branch: str
    target_branch: str
    state: str = "opened"
    reviewers: list[str] = field(default_factory=list)
    approved: bool = False
    discussions: list[dict[str, Any]] = field(default_factory=list)


class MRWorkflow:
    """Simulated merge-request workflow manager."""

    def __init__(self) -> None:
        self._mrs: dict[int, MR] = {}
        self._next_id = 1

    def create_mr(
        self,
        title: str,
        body: str,
        source: str,
        target: str = "main",
    ) -> MR:
        """Create a new merge request."""
        if not title:
            raise ValueError("MR title must not be empty")
        if not source:
            raise ValueError("Source branch must not be empty")
        if source == target:
            raise ValueError("Source and target branches must differ")

        mr = MR(
            id=self._next_id,
            title=title,
            description=body,
            source_branch=source,
            target_branch=target,
        )
        self._mrs[self._next_id] = mr
        self._next_id += 1
        return mr

    def auto_describe(self, diff: str) -> str:
        """Generate a description from a diff string (simulated AI summary)."""
        if not diff.strip():
            return "No changes detected."
        lines = diff.strip().splitlines()
        added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        return f"Auto-generated: {added} additions, {removed} deletions across {len(lines)} lines."

    def assign_reviewers(self, mr_id: int, reviewers: list[str]) -> bool:
        """Assign reviewers to an MR. Returns True on success."""
        mr = self._mrs.get(mr_id)
        if mr is None:
            raise KeyError(f"MR {mr_id} not found")
        if not reviewers:
            raise ValueError("Reviewers list must not be empty")
        mr.reviewers = list(reviewers)
        return True

    def approve(self, mr_id: int) -> bool:
        """Approve an MR. Returns True on success."""
        mr = self._mrs.get(mr_id)
        if mr is None:
            raise KeyError(f"MR {mr_id} not found")
        if mr.state != "opened":
            raise ValueError(f"Cannot approve MR in state '{mr.state}'")
        mr.approved = True
        return True

    def list_discussions(self, mr_id: int) -> list[dict[str, Any]]:
        """List discussion threads on an MR."""
        mr = self._mrs.get(mr_id)
        if mr is None:
            raise KeyError(f"MR {mr_id} not found")
        return list(mr.discussions)

    def _get_mr(self, mr_id: int) -> MR:
        """Get an MR by ID or raise KeyError."""
        mr = self._mrs.get(mr_id)
        if mr is None:
            raise KeyError(f"MR {mr_id} not found")
        return mr
