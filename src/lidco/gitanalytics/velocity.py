"""
Code Velocity — team velocity metrics from git history.

Computes commits/day, PRs merged/week, review turnaround, cycle time.
Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

_UTC = timezone.utc


@dataclass(frozen=True)
class VelocityMetrics:
    """Immutable velocity snapshot."""

    commits_per_day: float
    active_days: int
    total_commits: int
    period_days: int
    authors_active: int
    avg_commits_per_author: float
    busiest_day: str
    busiest_day_commits: int


@dataclass(frozen=True)
class CycleTimeMetrics:
    """Cycle time analysis results."""

    avg_cycle_hours: float
    median_cycle_hours: float
    p90_cycle_hours: float
    total_prs: int


class VelocityAnalyzer:
    """Compute team velocity metrics from a git repository."""

    def __init__(self, repo_path: str = ".") -> None:
        self._repo_path = repo_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        days: int = 30,
        since: str | None = None,
        until: str | None = None,
    ) -> VelocityMetrics:
        """Return velocity metrics for the given period."""
        if since is None:
            dt = datetime.now(tz=_UTC) - timedelta(days=days)
            since = dt.strftime("%Y-%m-%d")

        raw = self._git_log(since, until)
        commits = self._parse_commits(raw)

        if not commits:
            return VelocityMetrics(
                commits_per_day=0.0,
                active_days=0,
                total_commits=0,
                period_days=days,
                authors_active=0,
                avg_commits_per_author=0.0,
                busiest_day="",
                busiest_day_commits=0,
            )

        day_counts: dict[str, int] = {}
        authors: set[str] = set()
        for c in commits:
            day = c["date"][:10]
            day_counts[day] = day_counts.get(day, 0) + 1
            authors.add(c["email"])

        active_days = len(day_counts)
        total = len(commits)
        cpd = round(total / max(days, 1), 2)
        avg_per_author = round(total / max(len(authors), 1), 2)

        busiest = max(day_counts, key=day_counts.get)  # type: ignore[arg-type]
        busiest_count = day_counts[busiest]

        return VelocityMetrics(
            commits_per_day=cpd,
            active_days=active_days,
            total_commits=total,
            period_days=days,
            authors_active=len(authors),
            avg_commits_per_author=avg_per_author,
            busiest_day=busiest,
            busiest_day_commits=busiest_count,
        )

    def daily_breakdown(self, days: int = 14) -> list[dict[str, Any]]:
        """Return per-day commit counts for the last *days* days."""
        dt = datetime.now(tz=_UTC) - timedelta(days=days)
        since = dt.strftime("%Y-%m-%d")

        raw = self._git_log(since, None)
        commits = self._parse_commits(raw)

        day_counts: dict[str, int] = {}
        for c in commits:
            day = c["date"][:10]
            day_counts[day] = day_counts.get(day, 0) + 1

        result: list[dict[str, Any]] = []
        for i in range(days):
            d = (dt + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            result.append({"date": d, "commits": day_counts.get(d, 0)})
        return result

    def cycle_time(
        self, merge_log: list[dict[str, str]] | None = None
    ) -> CycleTimeMetrics:
        """Compute cycle time from a list of PR open/merge timestamps.

        Each entry: ``{"opened": "ISO", "merged": "ISO"}``.
        """
        if not merge_log:
            return CycleTimeMetrics(
                avg_cycle_hours=0.0,
                median_cycle_hours=0.0,
                p90_cycle_hours=0.0,
                total_prs=0,
            )

        hours: list[float] = []
        for pr in merge_log:
            try:
                opened = datetime.fromisoformat(pr["opened"])
                merged = datetime.fromisoformat(pr["merged"])
                delta = (merged - opened).total_seconds() / 3600
                hours.append(max(delta, 0.0))
            except (ValueError, KeyError):
                continue

        if not hours:
            return CycleTimeMetrics(
                avg_cycle_hours=0.0,
                median_cycle_hours=0.0,
                p90_cycle_hours=0.0,
                total_prs=0,
            )

        hours.sort()
        avg = round(sum(hours) / len(hours), 2)
        mid = len(hours) // 2
        median = round(
            hours[mid] if len(hours) % 2 else (hours[mid - 1] + hours[mid]) / 2,
            2,
        )
        p90_idx = int(len(hours) * 0.9)
        p90 = round(hours[min(p90_idx, len(hours) - 1)], 2)

        return CycleTimeMetrics(
            avg_cycle_hours=avg,
            median_cycle_hours=median,
            p90_cycle_hours=p90,
            total_prs=len(hours),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _git_log(self, since: str | None, until: str | None) -> str:
        cmd = [
            "git", "-C", self._repo_path, "log",
            "--format=%H|%an|%ae|%aI",
        ]
        if since:
            cmd.append(f"--since={since}")
        if until:
            cmd.append(f"--until={until}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _parse_commits(self, raw: str) -> list[dict[str, str]]:
        commits: list[dict[str, str]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append({
                    "hash": parts[0],
                    "name": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                })
        return commits
