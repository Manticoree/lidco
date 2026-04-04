"""HistoryAnalyzer — commit analytics, contributor stats, file churn, hotspots."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CommitRecord:
    """Immutable record of a single commit."""

    hash: str
    author: str
    date: datetime
    files: tuple[str, ...]
    message: str


class HistoryAnalyzer:
    """Analyse a stream of commits for contributor stats, churn and hotspots."""

    def __init__(self) -> None:
        self._commits: list[CommitRecord] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_commit(
        self,
        hash: str,
        author: str,
        date: datetime,
        files: list[str],
        message: str,
    ) -> None:
        """Add a commit to the analysis set."""
        if not hash:
            raise ValueError("hash must not be empty")
        if not author:
            raise ValueError("author must not be empty")
        record = CommitRecord(
            hash=hash,
            author=author,
            date=date,
            files=tuple(files),
            message=message,
        )
        self._commits.append(record)

    @property
    def commit_count(self) -> int:
        return len(self._commits)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def contributor_stats(self) -> dict[str, dict[str, Any]]:
        """Return per-author stats: commit_count, files_touched, first/last date."""
        stats: dict[str, dict[str, Any]] = {}
        for c in self._commits:
            if c.author not in stats:
                stats[c.author] = {
                    "commit_count": 0,
                    "files_touched": set(),
                    "first_date": c.date,
                    "last_date": c.date,
                }
            entry = stats[c.author]
            entry["commit_count"] += 1
            entry["files_touched"].update(c.files)
            if c.date < entry["first_date"]:
                entry["first_date"] = c.date
            if c.date > entry["last_date"]:
                entry["last_date"] = c.date
        # Convert sets to sorted lists for JSON-friendliness
        for entry in stats.values():
            entry["files_touched"] = sorted(entry["files_touched"])
        return stats

    def file_churn(self) -> list[tuple[str, int]]:
        """Return list of (file, change_count) sorted descending by count."""
        counts: dict[str, int] = {}
        for c in self._commits:
            for f in c.files:
                counts[f] = counts.get(f, 0) + 1
        return sorted(counts.items(), key=lambda x: (-x[1], x[0]))

    def hotspots(self, top_n: int = 10) -> list[tuple[str, int]]:
        """Return the top-N most changed files."""
        return self.file_churn()[:top_n]

    def release_cadence(self) -> dict[str, Any]:
        """Return stats about commit frequency over time."""
        if not self._commits:
            return {"total_commits": 0, "days_span": 0, "avg_per_day": 0.0}
        dates = sorted(c.date for c in self._commits)
        span = (dates[-1] - dates[0]).total_seconds() / 86400.0
        days_span = max(math.ceil(span), 1)
        return {
            "total_commits": len(self._commits),
            "days_span": days_span,
            "avg_per_day": round(len(self._commits) / days_span, 2),
            "first_date": dates[0].isoformat(),
            "last_date": dates[-1].isoformat(),
        }

    def summary(self) -> dict[str, Any]:
        """High-level summary combining all analytics."""
        return {
            "commit_count": self.commit_count,
            "contributor_count": len(self.contributor_stats()),
            "hotspots": self.hotspots(5),
            "cadence": self.release_cadence(),
        }
