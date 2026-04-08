"""History Digger — dig through project history to find design intent and key decisions.

Provides ``HistoryDigger`` that analyses git log output to build evolution
timelines, extract key decisions, and recover original design intent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CommitInfo:
    """Represents a single parsed commit."""

    sha: str
    author: str
    date: str
    message: str
    files_changed: tuple[str, ...] = ()

    def short_sha(self) -> str:
        """Return first 7 characters of the SHA."""
        return self.sha[:7]


@dataclass(frozen=True)
class DesignDecision:
    """A detected design decision extracted from history."""

    commit_sha: str
    date: str
    summary: str
    category: str  # e.g. "architecture", "api", "dependency", "refactor"
    confidence: float = 0.5  # 0.0–1.0

    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7


@dataclass
class EvolutionTimeline:
    """Timeline of how a file or module evolved."""

    target: str
    entries: list[CommitInfo] = field(default_factory=list)
    decisions: list[DesignDecision] = field(default_factory=list)

    @property
    def span(self) -> int:
        """Number of commits in the timeline."""
        return len(self.entries)

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [f"Timeline for '{self.target}': {self.span} commits"]
        for entry in self.entries:
            lines.append(f"  {entry.short_sha()} {entry.date} — {entry.message}")
        if self.decisions:
            lines.append(f"Key decisions: {len(self.decisions)}")
            for d in self.decisions:
                tag = "[HIGH]" if d.is_high_confidence() else "[LOW]"
                lines.append(f"  {tag} {d.summary} ({d.category})")
        return "\n".join(lines)


# ---- Decision detection keywords by category ----
_DECISION_PATTERNS: dict[str, list[str]] = {
    "architecture": [
        r"(?i)\brefactor\b",
        r"(?i)\brewrite\b",
        r"(?i)\brestructure\b",
        r"(?i)\bmigrat",
        r"(?i)\barchitect",
    ],
    "api": [
        r"(?i)\bapi\b",
        r"(?i)\bendpoint",
        r"(?i)\bschema\b",
        r"(?i)\bbreaking.change",
    ],
    "dependency": [
        r"(?i)\bupgrade\b",
        r"(?i)\bdependenc",
        r"(?i)\bbump\b",
        r"(?i)\bremove.dep",
    ],
    "refactor": [
        r"(?i)\bcleanup\b",
        r"(?i)\bextract\b",
        r"(?i)\brename\b",
        r"(?i)\bsimplify\b",
    ],
}


class HistoryDigger:
    """Dig through project history to find design intent and evolution.

    Parameters
    ----------
    commits:
        Pre-parsed commit list (newest-first).  In production this would
        come from ``git log``, but callers can inject parsed data directly.
    """

    def __init__(self, commits: list[CommitInfo] | None = None) -> None:
        self._commits: list[CommitInfo] = list(commits) if commits else []

    # -- public API --

    @property
    def commit_count(self) -> int:
        return len(self._commits)

    def add_commit(self, commit: CommitInfo) -> None:
        self._commits.append(commit)

    def timeline_for(self, target: str) -> EvolutionTimeline:
        """Build an evolution timeline for *target* (file path or keyword).

        Matches commits whose ``files_changed`` contain *target* **or**
        whose message mentions *target*.
        """
        matching = [
            c
            for c in self._commits
            if target in c.files_changed or target.lower() in c.message.lower()
        ]
        decisions = self._detect_decisions(matching)
        return EvolutionTimeline(target=target, entries=matching, decisions=decisions)

    def find_decisions(self) -> list[DesignDecision]:
        """Scan all commits and return detected design decisions."""
        return self._detect_decisions(self._commits)

    def original_intent(self, target: str) -> str:
        """Try to recover the original design intent for *target*.

        Returns the commit message of the earliest commit that mentions
        *target*, or a fallback message.
        """
        timeline = self.timeline_for(target)
        if not timeline.entries:
            return f"No history found for '{target}'."
        earliest = timeline.entries[-1]  # oldest
        return f"Original intent ({earliest.short_sha()}, {earliest.date}): {earliest.message}"

    def hot_files(self, top_n: int = 10) -> list[tuple[str, int]]:
        """Return most-frequently-changed files across all commits."""
        counts: dict[str, int] = {}
        for c in self._commits:
            for f in c.files_changed:
                counts[f] = counts.get(f, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_n]

    # -- private helpers --

    def _detect_decisions(self, commits: list[CommitInfo]) -> list[DesignDecision]:
        decisions: list[DesignDecision] = []
        for commit in commits:
            for category, patterns in _DECISION_PATTERNS.items():
                match_count = sum(
                    1 for p in patterns if re.search(p, commit.message)
                )
                if match_count > 0:
                    confidence = min(1.0, 0.4 + match_count * 0.2)
                    decisions.append(
                        DesignDecision(
                            commit_sha=commit.sha,
                            date=commit.date,
                            summary=commit.message.split("\n")[0][:120],
                            category=category,
                            confidence=confidence,
                        )
                    )
        return decisions
