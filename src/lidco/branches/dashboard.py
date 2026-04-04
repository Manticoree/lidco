"""Branch dashboard — overview, author activity, merge status.

Provides a read-only view of branch health for display in the CLI.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _DashboardBranch:
    name: str
    ahead: int
    behind: int
    author: str
    last_activity: float  # epoch


@dataclass
class BranchDashboard2:
    """Aggregate branch data for dashboard display."""

    _branches: list[_DashboardBranch] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def add_branch(
        self,
        name: str,
        ahead: int = 0,
        behind: int = 0,
        author: str = "",
        last_activity: float = 0.0,
    ) -> None:
        self._branches.append(
            _DashboardBranch(
                name=name,
                ahead=ahead,
                behind=behind,
                author=author,
                last_activity=last_activity,
            )
        )

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    def overview(self) -> list[dict]:
        """Return a list of dicts summarising every tracked branch."""
        return [
            {
                "name": b.name,
                "ahead": b.ahead,
                "behind": b.behind,
                "author": b.author,
                "last_activity": b.last_activity,
            }
            for b in self._branches
        ]

    def active_authors(self) -> list[str]:
        """Return a deduplicated, sorted list of authors with branches."""
        return sorted({b.author for b in self._branches if b.author})

    def merge_status(self) -> dict:
        """Return counts of branches that are ahead-only, behind, or diverged."""
        ahead_only = 0
        behind_only = 0
        diverged = 0
        up_to_date = 0
        for b in self._branches:
            if b.ahead > 0 and b.behind > 0:
                diverged += 1
            elif b.ahead > 0:
                ahead_only += 1
            elif b.behind > 0:
                behind_only += 1
            else:
                up_to_date += 1
        return {
            "ahead_only": ahead_only,
            "behind_only": behind_only,
            "diverged": diverged,
            "up_to_date": up_to_date,
        }

    def summary(self) -> dict:
        """Return a high-level summary dict."""
        return {
            "total": len(self._branches),
            "authors": len(self.active_authors()),
            "merge_status": self.merge_status(),
        }
