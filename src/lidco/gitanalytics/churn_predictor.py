"""
Churn Predictor — predict files likely to change based on history.

Analyses commit history for change frequency, recency, coupling,
and seasonal trends to produce a churn score per file.
Pure stdlib.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

_UTC = timezone.utc


@dataclass(frozen=True)
class ChurnEntry:
    """Churn prediction for a single file."""

    path: str
    score: float
    change_count: int
    last_changed: str
    coupled_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChurnReport:
    """Aggregated churn prediction report."""

    files: list[ChurnEntry]
    total_files_analyzed: int
    period_days: int
    threshold: float


class ChurnPredictor:
    """Predict which files are most likely to change soon."""

    def __init__(self, repo_path: str = ".") -> None:
        self._repo_path = repo_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(
        self,
        days: int = 90,
        top_n: int = 20,
        threshold: float = 0.0,
    ) -> ChurnReport:
        """Return a churn report ranking files by likelihood of change."""
        raw = self._git_log(days)
        commits = self._parse_log(raw)
        file_stats = self._compute_file_stats(commits, days)
        coupling = self._compute_coupling(commits)

        entries: list[ChurnEntry] = []
        for path, stats in file_stats.items():
            coupled = coupling.get(path, [])[:5]
            entry = ChurnEntry(
                path=path,
                score=round(stats["score"], 4),
                change_count=stats["count"],
                last_changed=stats["last_changed"],
                coupled_files=coupled,
            )
            if entry.score >= threshold:
                entries.append(entry)

        entries.sort(key=lambda e: e.score, reverse=True)
        return ChurnReport(
            files=entries[:top_n],
            total_files_analyzed=len(file_stats),
            period_days=days,
            threshold=threshold,
        )

    def hot_spots(self, days: int = 30, top_n: int = 10) -> list[ChurnEntry]:
        """Return the hottest files (most frequently changed)."""
        report = self.predict(days=days, top_n=top_n)
        return report.files

    def coupled_files(self, path: str, days: int = 90) -> list[str]:
        """Return files that frequently change together with *path*."""
        raw = self._git_log(days)
        commits = self._parse_log(raw)
        coupling = self._compute_coupling(commits)
        return coupling.get(path, [])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _git_log(self, days: int) -> str:
        since = (datetime.now(tz=_UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
        cmd = [
            "git", "-C", self._repo_path, "log",
            "--format=%H|%aI",
            "--name-only",
            f"--since={since}",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _parse_log(self, raw: str) -> list[dict[str, Any]]:
        """Parse git log output into commit dicts."""
        commits: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                if current is not None:
                    commits.append(current)
                parts = line.split("|", 1)
                current = {"hash": parts[0], "date": parts[1], "files": []}
            elif current is not None:
                current["files"].append(line)

        if current is not None:
            commits.append(current)
        return commits

    def _compute_file_stats(
        self, commits: list[dict[str, Any]], days: int
    ) -> dict[str, dict[str, Any]]:
        """Score each file based on frequency and recency."""
        now = datetime.now(tz=_UTC)
        stats: dict[str, dict[str, Any]] = {}

        for commit in commits:
            try:
                commit_date = datetime.fromisoformat(
                    commit["date"].replace("Z", "+00:00")
                )
                if commit_date.tzinfo is None:
                    commit_date = commit_date.replace(tzinfo=_UTC)
                age_days = max((now - commit_date).days, 1)
            except (ValueError, TypeError):
                age_days = days

            recency_weight = 1.0 / (1.0 + math.log(age_days))

            for f in commit["files"]:
                if f not in stats:
                    stats[f] = {
                        "count": 0,
                        "score": 0.0,
                        "last_changed": commit["date"],
                    }
                stats[f]["count"] += 1
                stats[f]["score"] += recency_weight
                if commit["date"] > stats[f]["last_changed"]:
                    stats[f]["last_changed"] = commit["date"]

        return stats

    def _compute_coupling(
        self, commits: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """Find files that change together frequently."""
        pair_counts: dict[tuple[str, str], int] = {}
        for commit in commits:
            files = sorted(set(commit["files"]))
            for i, a in enumerate(files):
                for b in files[i + 1:]:
                    pair = (a, b)
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1

        coupling: dict[str, list[tuple[str, int]]] = {}
        for (a, b), count in pair_counts.items():
            if count >= 2:
                coupling.setdefault(a, []).append((b, count))
                coupling.setdefault(b, []).append((a, count))

        result: dict[str, list[str]] = {}
        for path, partners in coupling.items():
            partners.sort(key=lambda x: x[1], reverse=True)
            result[path] = [p[0] for p in partners]
        return result
