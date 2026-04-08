"""Review Analytics — Review quality metrics and improvement trends (Q332, task 1775)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewEvent:
    """A single code review event for analytics tracking."""

    review_id: str
    reviewer: str
    pr_id: str
    issues_found: int = 0
    issues_adopted: int = 0
    review_time_seconds: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            object.__setattr__(self, "timestamp", time.time())

    @property
    def adoption_rate(self) -> float:
        if self.issues_found == 0:
            return 0.0
        return round(self.issues_adopted / self.issues_found, 4)


@dataclass(frozen=True)
class ReviewerStats:
    """Aggregated stats for one reviewer."""

    reviewer: str
    total_reviews: int
    total_issues: int
    total_adopted: int
    avg_review_time: float
    adoption_rate: float


@dataclass(frozen=True)
class IssueSummary:
    """Summary of a common issue type."""

    issue_type: str
    count: int
    adoption_rate: float


@dataclass(frozen=True)
class TrendPoint:
    """A single data point in a trend."""

    period: str
    value: float


class ReviewAnalytics:
    """Tracks and analyses code review quality metrics."""

    def __init__(self) -> None:
        self._events: list[ReviewEvent] = []
        self._issue_types: dict[str, list[bool]] = {}  # type -> [adopted?]

    def record_event(self, event: ReviewEvent) -> None:
        """Record a review event."""
        self._events = [*self._events, event]

    def record_issue(self, issue_type: str, adopted: bool = False) -> None:
        """Record an issue type occurrence and whether it was adopted."""
        existing = self._issue_types.get(issue_type, [])
        self._issue_types = {
            **self._issue_types,
            issue_type: [*existing, adopted],
        }

    @property
    def event_count(self) -> int:
        return len(self._events)

    def reviewer_stats(self, reviewer: str) -> ReviewerStats | None:
        """Get aggregated stats for a reviewer."""
        events = [e for e in self._events if e.reviewer == reviewer]
        if not events:
            return None
        total_issues = sum(e.issues_found for e in events)
        total_adopted = sum(e.issues_adopted for e in events)
        total_time = sum(e.review_time_seconds for e in events)
        return ReviewerStats(
            reviewer=reviewer,
            total_reviews=len(events),
            total_issues=total_issues,
            total_adopted=total_adopted,
            avg_review_time=round(total_time / len(events), 2),
            adoption_rate=round(total_adopted / total_issues, 4) if total_issues else 0.0,
        )

    def list_reviewers(self) -> list[str]:
        """Return sorted list of unique reviewers."""
        return sorted({e.reviewer for e in self._events})

    def common_issues(self, top_n: int = 10) -> list[IssueSummary]:
        """Return the most common issue types."""
        summaries: list[IssueSummary] = []
        for issue_type, adoptions in self._issue_types.items():
            count = len(adoptions)
            adopted_count = sum(1 for a in adoptions if a)
            rate = round(adopted_count / count, 4) if count else 0.0
            summaries.append(IssueSummary(issue_type=issue_type, count=count, adoption_rate=rate))
        summaries.sort(key=lambda s: -s.count)
        return summaries[:top_n]

    def adoption_rate(self) -> float:
        """Overall feedback adoption rate."""
        total = sum(e.issues_found for e in self._events)
        adopted = sum(e.issues_adopted for e in self._events)
        if total == 0:
            return 0.0
        return round(adopted / total, 4)

    def average_review_time(self) -> float:
        """Average review time in seconds."""
        if not self._events:
            return 0.0
        return round(sum(e.review_time_seconds for e in self._events) / len(self._events), 2)

    def improvement_trend(self, reviewer: str | None = None, periods: int = 5) -> list[TrendPoint]:
        """Return adoption rate trend split into N equal periods."""
        events = self._events
        if reviewer is not None:
            events = [e for e in events if e.reviewer == reviewer]
        if not events:
            return []

        events_sorted = sorted(events, key=lambda e: e.timestamp)
        chunk_size = max(1, len(events_sorted) // periods)
        trend: list[TrendPoint] = []

        for i in range(0, len(events_sorted), chunk_size):
            chunk = events_sorted[i : i + chunk_size]
            total = sum(e.issues_found for e in chunk)
            adopted = sum(e.issues_adopted for e in chunk)
            rate = round(adopted / total, 4) if total else 0.0
            trend.append(TrendPoint(period=f"period-{len(trend) + 1}", value=rate))

        return trend[:periods]

    def summary(self) -> dict[str, Any]:
        """Return a summary dict of analytics."""
        return {
            "total_reviews": self.event_count,
            "unique_reviewers": len(self.list_reviewers()),
            "adoption_rate": self.adoption_rate(),
            "avg_review_time": self.average_review_time(),
            "common_issues": len(self._issue_types),
        }
