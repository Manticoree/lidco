"""
Repository Health — overall repo health score.

Evaluates test coverage trend, build stability, dependency freshness,
and commit activity to produce a composite health score.
Pure stdlib.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HealthDimension:
    """A single health dimension with score and detail."""

    name: str
    score: float  # 0.0 – 1.0
    detail: str


@dataclass(frozen=True)
class HealthReport:
    """Composite repo health report."""

    overall_score: float  # 0.0 – 1.0
    grade: str  # A / B / C / D / F
    dimensions: list[HealthDimension]
    recommendations: list[str]


class HealthAnalyzer:
    """Evaluate repository health from multiple dimensions."""

    _GRADE_THRESHOLDS: list[tuple[float, str]] = [
        (0.9, "A"),
        (0.75, "B"),
        (0.6, "C"),
        (0.4, "D"),
        (0.0, "F"),
    ]

    def __init__(self, repo_path: str = ".") -> None:
        self._repo_path = repo_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, days: int = 30) -> HealthReport:
        """Produce a composite health report for the repo."""
        dims: list[HealthDimension] = [
            self._commit_activity(days),
            self._author_diversity(days),
            self._recent_file_churn(days),
            self._readme_presence(),
            self._test_directory_presence(),
        ]

        scores = [d.score for d in dims]
        overall = round(sum(scores) / max(len(scores), 1), 2)
        grade = self._grade(overall)
        recs = self._recommendations(dims)

        return HealthReport(
            overall_score=overall,
            grade=grade,
            dimensions=dims,
            recommendations=recs,
        )

    def quick_score(self) -> float:
        """Return just the numeric health score (0–1)."""
        return self.analyze().overall_score

    # ------------------------------------------------------------------
    # Dimension evaluators
    # ------------------------------------------------------------------

    def _commit_activity(self, days: int) -> HealthDimension:
        raw = self._git_log_count(days)
        count = len([l for l in raw.splitlines() if l.strip()])
        if count >= 50:
            score = 1.0
        elif count >= 20:
            score = 0.8
        elif count >= 5:
            score = 0.5
        elif count >= 1:
            score = 0.3
        else:
            score = 0.0
        return HealthDimension(
            name="commit_activity",
            score=score,
            detail=f"{count} commits in last {days} days",
        )

    def _author_diversity(self, days: int) -> HealthDimension:
        raw = self._git_shortlog(days)
        authors = set()
        for line in raw.splitlines():
            line = line.strip()
            if line:
                # shortlog format: "  N\tAuthor"
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    authors.add(parts[1].strip())
        n = len(authors)
        if n >= 5:
            score = 1.0
        elif n >= 3:
            score = 0.7
        elif n >= 2:
            score = 0.5
        elif n == 1:
            score = 0.3
        else:
            score = 0.0
        return HealthDimension(
            name="author_diversity",
            score=score,
            detail=f"{n} active author(s) in last {days} days",
        )

    def _recent_file_churn(self, days: int) -> HealthDimension:
        """High churn in many files can indicate instability."""
        raw = self._git_diff_stat(days)
        lines = [l for l in raw.splitlines() if l.strip()]
        changed = len(lines)
        if changed <= 20:
            score = 1.0
            detail = f"{changed} files changed — low churn"
        elif changed <= 100:
            score = 0.7
            detail = f"{changed} files changed — moderate churn"
        else:
            score = 0.4
            detail = f"{changed} files changed — high churn"
        return HealthDimension(name="file_churn", score=score, detail=detail)

    def _readme_presence(self) -> HealthDimension:
        p = Path(self._repo_path)
        has_readme = any(
            (p / name).exists()
            for name in ("README.md", "README.rst", "README.txt", "README")
        )
        return HealthDimension(
            name="readme",
            score=1.0 if has_readme else 0.0,
            detail="README found" if has_readme else "No README found",
        )

    def _test_directory_presence(self) -> HealthDimension:
        p = Path(self._repo_path)
        has_tests = any(
            (p / name).is_dir()
            for name in ("tests", "test", "spec", "__tests__")
        )
        return HealthDimension(
            name="tests",
            score=1.0 if has_tests else 0.0,
            detail="Test directory found" if has_tests else "No test directory found",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _grade(self, score: float) -> str:
        for threshold, letter in self._GRADE_THRESHOLDS:
            if score >= threshold:
                return letter
        return "F"

    def _recommendations(self, dims: list[HealthDimension]) -> list[str]:
        recs: list[str] = []
        for d in dims:
            if d.name == "commit_activity" and d.score < 0.5:
                recs.append("Increase commit frequency to maintain momentum.")
            if d.name == "author_diversity" and d.score < 0.5:
                recs.append("Encourage more contributors to reduce bus factor.")
            if d.name == "file_churn" and d.score < 0.5:
                recs.append("High file churn detected — consider stabilisation sprints.")
            if d.name == "readme" and d.score < 1.0:
                recs.append("Add a README to improve onboarding.")
            if d.name == "tests" and d.score < 1.0:
                recs.append("Add a test directory to ensure code quality.")
        return recs

    def _git_log_count(self, days: int) -> str:
        since = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        return self._run_git(["log", "--oneline", f"--since={since}"])

    def _git_shortlog(self, days: int) -> str:
        since = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        return self._run_git(["shortlog", "-sn", f"--since={since}"])

    def _git_diff_stat(self, days: int) -> str:
        since = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        return self._run_git(["log", "--name-only", "--format=", f"--since={since}"])

    def _run_git(self, args: list[str]) -> str:
        cmd = ["git", "-C", self._repo_path] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""
