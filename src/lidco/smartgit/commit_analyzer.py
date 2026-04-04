"""CommitAnalyzer — classify staged diffs and suggest commit messages.

Stdlib only.  No mutation of input data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnalysisResult:
    """Immutable result of a diff analysis."""

    category: str  # feat / fix / refactor / docs / test / chore
    scope: str  # e.g. "auth", "cli", ""
    message: str  # suggested one-liner
    files: List[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0


# ---------------------------------------------------------------------------
# Heuristic maps
# ---------------------------------------------------------------------------

_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("test", re.compile(r"(test_|_test\.py|tests/|\.test\.|spec\.)", re.IGNORECASE)),
    ("docs", re.compile(r"\.(md|rst|txt|adoc)$|README|CHANGELOG|docs/", re.IGNORECASE)),
    ("fix", re.compile(r"\bfix(es|ed)?\b|\bbug\b|\bpatch\b|\bhotfix\b", re.IGNORECASE)),
    ("refactor", re.compile(r"\brefactor\b|\brename\b|\bmove\b|\breorganize\b", re.IGNORECASE)),
    ("feat", re.compile(r"\badd\b|\bnew\b|\bfeature\b|\bimplement\b", re.IGNORECASE)),
]

_SCOPE_DIRS = re.compile(r"^(?:src/\w+/)?(\w+)/")


# ---------------------------------------------------------------------------
# CommitAnalyzer
# ---------------------------------------------------------------------------

class CommitAnalyzer:
    """Analyse a unified diff string and suggest commit metadata."""

    def classify(self, diff: str) -> str:
        """Return the conventional-commit *type* (feat/fix/refactor/docs/test/chore)."""
        for category, pattern in _CATEGORY_PATTERNS:
            if pattern.search(diff):
                return category
        return "chore"

    def extract_scope(self, diff: str) -> str:
        """Best-effort scope from file paths in the diff."""
        files = self._extract_files(diff)
        scopes: list[str] = []
        for f in files:
            m = _SCOPE_DIRS.search(f)
            if m:
                scopes.append(m.group(1))
        if not scopes:
            return ""
        # Return the most common scope.
        from collections import Counter
        most_common = Counter(scopes).most_common(1)
        return most_common[0][0] if most_common else ""

    def suggest_message(self, diff: str) -> str:
        """Return a one-line conventional commit message."""
        category = self.classify(diff)
        scope = self.extract_scope(diff)
        files = self._extract_files(diff)
        adds, dels = self._count_changes(diff)

        if scope:
            prefix = f"{category}({scope})"
        else:
            prefix = category

        if len(files) == 1:
            detail = f"update {files[0]}"
        elif files:
            detail = f"update {len(files)} files"
        else:
            detail = "update code"

        stats = f"(+{adds}/-{dels})"
        return f"{prefix}: {detail} {stats}"

    def analyze(self, diff: str) -> AnalysisResult:
        """Full analysis returning an *AnalysisResult*."""
        files = self._extract_files(diff)
        adds, dels = self._count_changes(diff)
        return AnalysisResult(
            category=self.classify(diff),
            scope=self.extract_scope(diff),
            message=self.suggest_message(diff),
            files=files,
            additions=adds,
            deletions=dels,
        )

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _extract_files(diff: str) -> list[str]:
        """Parse file paths from ``--- a/…`` / ``+++ b/…`` headers."""
        seen: set[str] = set()
        out: list[str] = []
        for m in re.finditer(r"^(?:\+\+\+|---)\s+[ab]/(.+)$", diff, re.MULTILINE):
            path = m.group(1)
            if path not in seen and path != "/dev/null":
                seen.add(path)
                out.append(path)
        return out

    @staticmethod
    def _count_changes(diff: str) -> tuple[int, int]:
        adds = 0
        dels = 0
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                adds += 1
            elif line.startswith("-") and not line.startswith("---"):
                dels += 1
        return adds, dels
