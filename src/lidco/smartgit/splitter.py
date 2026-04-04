"""CommitSplitter — split large diffs into logical commit groups.

Stdlib only.  No mutation of input data.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileGroup:
    """A group of files sharing a common directory."""

    directory: str
    files: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class FeatureGroup:
    """A group of files related to the same feature (heuristic)."""

    feature: str
    files: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommitGroup:
    """One proposed commit within a split plan."""

    label: str
    files: List[str] = field(default_factory=list)
    reason: str = ""


# ---------------------------------------------------------------------------
# Feature keyword map (lowercased stems)
# ---------------------------------------------------------------------------

_FEATURE_KEYWORDS: list[tuple[str, re.Pattern[str]]] = [
    ("test", re.compile(r"test_|_test\.|tests/|spec\.", re.IGNORECASE)),
    ("docs", re.compile(r"\.(md|rst|txt|adoc)$|README|CHANGELOG|docs/", re.IGNORECASE)),
    ("config", re.compile(r"config|settings|\.env|\.toml|\.yaml|\.yml", re.IGNORECASE)),
    ("ci", re.compile(r"\.github/|\.gitlab-ci|Jenkinsfile|\.circleci", re.IGNORECASE)),
]


# ---------------------------------------------------------------------------
# CommitSplitter
# ---------------------------------------------------------------------------

class CommitSplitter:
    """Propose ways to split a large changeset into smaller commits."""

    def split_by_file(self, files: List[str]) -> List[FileGroup]:
        """Group *files* by their immediate parent directory."""
        buckets: Dict[str, list[str]] = {}
        for f in files:
            directory = os.path.dirname(f) or "."
            buckets.setdefault(directory, []).append(f)
        return [
            FileGroup(directory=d, files=sorted(fs))
            for d, fs in sorted(buckets.items())
        ]

    def split_by_feature(
        self, files: List[str], diff: str = ""
    ) -> List[FeatureGroup]:
        """Group *files* by heuristic feature keywords."""
        assigned: dict[str, list[str]] = {}
        unmatched: list[str] = []

        for f in files:
            matched = False
            for feature, pattern in _FEATURE_KEYWORDS:
                if pattern.search(f):
                    assigned.setdefault(feature, []).append(f)
                    matched = True
                    break
            if not matched:
                unmatched.append(f)

        groups: list[FeatureGroup] = [
            FeatureGroup(feature=feat, files=sorted(fs))
            for feat, fs in sorted(assigned.items())
        ]
        if unmatched:
            groups.append(FeatureGroup(feature="code", files=sorted(unmatched)))
        return groups

    def suggest_splits(self, diff: str) -> List[CommitGroup]:
        """Parse a unified diff and propose *CommitGroup* splits."""
        files = self._extract_files(diff)
        if len(files) <= 1:
            return [
                CommitGroup(
                    label="single",
                    files=files,
                    reason="Only one file changed — no split needed.",
                )
            ]

        feature_groups = self.split_by_feature(files, diff)
        return [
            CommitGroup(
                label=fg.feature,
                files=fg.files,
                reason=f"Files related to '{fg.feature}'.",
            )
            for fg in feature_groups
        ]

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _extract_files(diff: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in re.finditer(r"^(?:\+\+\+|---)\s+[ab]/(.+)$", diff, re.MULTILINE):
            path = m.group(1)
            if path not in seen and path != "/dev/null":
                seen.add(path)
                out.append(path)
        return out
