"""Commit history analysis — Task 335."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections import Counter
from typing import Sequence


_CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|refactor|docs|test|chore|perf|ci|build|style|revert)(\(.+\))?!?:"
)


@dataclass(frozen=True)
class CommitRecord:
    hash: str
    message: str
    author: str
    timestamp: str = ""
    files_changed: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CommitStats:
    total_commits: int
    authors: dict[str, int]
    churn_files: list[tuple[str, int]]
    message_quality: float  # 0.0–1.0 average


class CommitAnalyzer:
    """Analyzes a list of CommitRecords to produce summary statistics."""

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def analyze(self, records: Sequence[CommitRecord]) -> CommitStats:
        """Return statistics derived from the given commit records."""
        if not records:
            return CommitStats(
                total_commits=0,
                authors={},
                churn_files=[],
                message_quality=0.0,
            )

        author_counts: Counter[str] = Counter()
        file_counts: Counter[str] = Counter()
        quality_scores: list[float] = []

        for rec in records:
            author_counts[rec.author] += 1
            for f in rec.files_changed:
                file_counts[f] += 1
            quality_scores.append(self.score_message(rec.message))

        churn_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        avg_quality = sum(quality_scores) / len(quality_scores)

        return CommitStats(
            total_commits=len(records),
            authors=dict(author_counts),
            churn_files=churn_files,
            message_quality=round(avg_quality, 4),
        )

    def score_message(self, message: str) -> float:
        """Return quality score for a commit message (0.0, 0.5, or 1.0)."""
        if not message or not message.strip():
            return 0.0
        if _CONVENTIONAL_RE.match(message.strip()):
            return 1.0
        return 0.5

    def parse_git_log(self, output: str) -> list[CommitRecord]:
        """Parse ``git log --format=...`` output into CommitRecord list.

        Expected per-commit format (fields separated by newlines)::

            COMMIT:<hash>
            AUTHOR:<name>
            DATE:<iso>
            MESSAGE:<subject>
            FILES:
            <file1>
            <file2>
            (blank line)
        """
        if not output or not output.strip():
            return []

        records: list[CommitRecord] = []
        current: dict = {}
        files: list[str] = []
        in_files = False

        for line in output.splitlines():
            if line.startswith("COMMIT:"):
                if current.get("hash"):
                    records.append(
                        CommitRecord(
                            hash=current["hash"],
                            message=current.get("message", ""),
                            author=current.get("author", ""),
                            timestamp=current.get("date", ""),
                            files_changed=tuple(files),
                        )
                    )
                current = {"hash": line[7:].strip()}
                files = []
                in_files = False
            elif line.startswith("AUTHOR:"):
                current["author"] = line[7:].strip()
                in_files = False
            elif line.startswith("DATE:"):
                current["date"] = line[5:].strip()
                in_files = False
            elif line.startswith("MESSAGE:"):
                current["message"] = line[8:].strip()
                in_files = False
            elif line.startswith("FILES:"):
                in_files = True
            elif in_files and line.strip():
                files.append(line.strip())

        if current.get("hash"):
            records.append(
                CommitRecord(
                    hash=current["hash"],
                    message=current.get("message", ""),
                    author=current.get("author", ""),
                    timestamp=current.get("date", ""),
                    files_changed=tuple(files),
                )
            )

        return records
