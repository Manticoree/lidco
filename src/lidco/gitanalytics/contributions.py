"""
Contribution Analytics — per-author stats from git log.

Parses git log output to compute lines added/removed, files touched,
commit frequency, and review activity per author.  Pure stdlib.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuthorStats:
    """Immutable stats for a single author."""

    name: str
    email: str
    commits: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    files_touched: int = 0
    first_commit: str = ""
    last_commit: str = ""
    reviews: int = 0


@dataclass(frozen=True)
class ContributionSummary:
    """Aggregate contribution summary for the whole repo."""

    total_commits: int
    total_authors: int
    authors: list[AuthorStats]
    period_start: str
    period_end: str


class ContributionAnalyzer:
    """Analyse per-author contribution stats from a git repository."""

    def __init__(self, repo_path: str = ".") -> None:
        self._repo_path = repo_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, since: str | None = None, until: str | None = None) -> ContributionSummary:
        """Return contribution summary for the repository.

        *since* / *until* are ISO date strings forwarded to ``git log``.
        """
        raw_log = self._git_log(since, until)
        entries = self._parse_log(raw_log)
        author_map: dict[str, dict[str, Any]] = {}

        for entry in entries:
            key = entry["email"]
            if key not in author_map:
                author_map[key] = {
                    "name": entry["name"],
                    "email": entry["email"],
                    "commits": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "files": set(),
                    "first_commit": entry["date"],
                    "last_commit": entry["date"],
                    "reviews": 0,
                }
            rec = author_map[key]
            rec["commits"] += 1
            rec["lines_added"] += entry["added"]
            rec["lines_removed"] += entry["removed"]
            rec["files"].update(entry["files"])
            if entry["date"] < rec["first_commit"]:
                rec["first_commit"] = entry["date"]
            if entry["date"] > rec["last_commit"]:
                rec["last_commit"] = entry["date"]
            if entry.get("is_review"):
                rec["reviews"] += 1

        authors = sorted(
            [
                AuthorStats(
                    name=v["name"],
                    email=v["email"],
                    commits=v["commits"],
                    lines_added=v["lines_added"],
                    lines_removed=v["lines_removed"],
                    files_touched=len(v["files"]),
                    first_commit=v["first_commit"],
                    last_commit=v["last_commit"],
                    reviews=v["reviews"],
                )
                for v in author_map.values()
            ],
            key=lambda a: a.commits,
            reverse=True,
        )

        dates = [e["date"] for e in entries] if entries else ["", ""]
        return ContributionSummary(
            total_commits=len(entries),
            total_authors=len(authors),
            authors=authors,
            period_start=min(dates) if dates else "",
            period_end=max(dates) if dates else "",
        )

    def top_authors(self, n: int = 10, since: str | None = None) -> list[AuthorStats]:
        """Return the top *n* authors by commit count."""
        summary = self.analyze(since=since)
        return summary.authors[:n]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _git_log(self, since: str | None, until: str | None) -> str:
        cmd = [
            "git", "-C", self._repo_path, "log",
            "--format=%H|%an|%ae|%aI|%s",
            "--numstat",
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

    def _parse_log(self, raw: str) -> list[dict[str, Any]]:
        """Parse ``git log --format=... --numstat`` output."""
        entries: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" in line and line.count("|") >= 4:
                # header line
                if current is not None:
                    entries.append(current)
                parts = line.split("|", 4)
                subject = parts[4] if len(parts) > 4 else ""
                current = {
                    "hash": parts[0],
                    "name": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "subject": subject,
                    "added": 0,
                    "removed": 0,
                    "files": [],
                    "is_review": "review" in subject.lower(),
                }
            elif current is not None:
                # numstat line: <added>\t<removed>\t<file>
                stat_parts = line.split("\t")
                if len(stat_parts) >= 3:
                    try:
                        added = int(stat_parts[0])
                    except ValueError:
                        added = 0
                    try:
                        removed = int(stat_parts[1])
                    except ValueError:
                        removed = 0
                    current["added"] += added
                    current["removed"] += removed
                    current["files"].append(stat_parts[2])

        if current is not None:
            entries.append(current)

        return entries
