"""PRStatusTracker — track PR readiness: CI, reviews, merge eligibility (stdlib only)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class CIStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


@dataclass
class ReviewState:
    """One reviewer's state."""
    reviewer: str
    approved: bool = False
    reviewed_at: float = 0.0


@dataclass
class PRStatus:
    """Aggregated PR status."""
    pr_id: str
    ci_status: CIStatus = CIStatus.PENDING
    reviews: dict[str, ReviewState] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    required_approvals: int = 1

    @property
    def approval_count(self) -> int:
        return sum(1 for r in self.reviews.values() if r.approved)

    @property
    def is_approved(self) -> bool:
        return self.approval_count >= self.required_approvals

    @property
    def ci_passed(self) -> bool:
        return self.ci_status == CIStatus.PASSED


class PRStatusTracker:
    """Track PR status including CI results and reviewer approvals.

    All state is kept in-memory.
    """

    def __init__(self, required_approvals: int = 1) -> None:
        self._prs: dict[str, PRStatus] = {}
        self._required_approvals = required_approvals

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def track(self, pr_id: str) -> PRStatus:
        """Start tracking a PR or return existing status."""
        if pr_id not in self._prs:
            self._prs = {
                **self._prs,
                pr_id: PRStatus(pr_id=pr_id, required_approvals=self._required_approvals),
            }
        return self._prs[pr_id]

    def update_ci(self, pr_id: str, status: str) -> PRStatus:
        """Update CI status for a tracked PR.

        Parameters
        ----------
        status:
            One of 'pending', 'running', 'passed', 'failed'.
        """
        pr = self.track(pr_id)
        try:
            ci = CIStatus(status)
        except ValueError:
            raise ValueError(f"Invalid CI status: {status!r}. Use: pending/running/passed/failed.")
        # Immutable update
        new_pr = PRStatus(
            pr_id=pr.pr_id,
            ci_status=ci,
            reviews=pr.reviews,
            created_at=pr.created_at,
            required_approvals=pr.required_approvals,
        )
        self._prs = {**self._prs, pr_id: new_pr}
        return new_pr

    def update_review(self, pr_id: str, reviewer: str, approved: bool) -> PRStatus:
        """Record a review for a PR."""
        pr = self.track(pr_id)
        new_reviews = {
            **pr.reviews,
            reviewer: ReviewState(reviewer=reviewer, approved=approved, reviewed_at=time.time()),
        }
        new_pr = PRStatus(
            pr_id=pr.pr_id,
            ci_status=pr.ci_status,
            reviews=new_reviews,
            created_at=pr.created_at,
            required_approvals=pr.required_approvals,
        )
        self._prs = {**self._prs, pr_id: new_pr}
        return new_pr

    def is_ready(self, pr_id: str) -> bool:
        """Return True if the PR has passed CI and has enough approvals."""
        pr = self.track(pr_id)
        return pr.ci_passed and pr.is_approved

    def auto_merge_eligible(self, pr_id: str) -> bool:
        """Return True if the PR is ready and has no rejections."""
        pr = self.track(pr_id)
        if not self.is_ready(pr_id):
            return False
        # No rejections
        for r in pr.reviews.values():
            if not r.approved:
                return False
        return True

    def get(self, pr_id: str) -> PRStatus | None:
        """Return PR status or None if not tracked."""
        return self._prs.get(pr_id)

    def list_tracked(self) -> list[str]:
        """Return list of tracked PR IDs."""
        return list(self._prs.keys())
