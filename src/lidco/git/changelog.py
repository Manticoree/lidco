"""
Changelog Generator — conventional-changelog parity.

Parses git log for Conventional Commits (https://www.conventionalcommits.org/)
and groups them into CHANGELOG sections.

Commit format:
  <type>[optional scope]: <description>
  [optional body]
  [optional footer(s)]

Types mapped to sections:
  feat     → Features
  fix      → Bug Fixes
  docs     → Documentation
  style    → Style
  refactor → Refactoring
  perf     → Performance
  test     → Tests
  chore    → Chores
  ci       → CI/CD
  build    → Build
  BREAKING → Breaking Changes (any type with "!" or "BREAKING CHANGE" footer)
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConventionalCommit:
    hash: str
    type: str           # feat | fix | docs | ...
    scope: str          # optional, e.g. "auth" in "feat(auth):"
    description: str
    body: str
    breaking: bool
    date: str
    author: str
    raw_message: str


@dataclass
class ChangelogSection:
    title: str
    commits: list[ConventionalCommit] = field(default_factory=list)


@dataclass
class ChangelogRelease:
    version: str        # e.g. "v1.2.0" or "Unreleased"
    date: str
    sections: list[ChangelogSection] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(s.commits for s in self.sections)


@dataclass
class ChangelogResult:
    releases: list[ChangelogRelease]
    unrecognized_commits: list[str]  # commits that didn't match the pattern

    def to_markdown(self) -> str:
        lines = ["# Changelog", ""]
        for release in self.releases:
            if release.is_empty():
                continue
            lines.append(f"## {release.version} ({release.date})")
            lines.append("")
            for section in release.sections:
                if not section.commits:
                    continue
                lines.append(f"### {section.title}")
                lines.append("")
                for commit in section.commits:
                    scope = f"**{commit.scope}**: " if commit.scope else ""
                    breaking = " ⚠️ BREAKING" if commit.breaking else ""
                    lines.append(
                        f"- {scope}{commit.description}"
                        f" ([{commit.hash[:8]}]){breaking}"
                    )
                lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Conventional commit parser
# ---------------------------------------------------------------------------

# Type → display title
_TYPE_MAP: dict[str, str] = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "doc": "Documentation",
    "style": "Style",
    "refactor": "Refactoring",
    "perf": "Performance",
    "test": "Tests",
    "chore": "Chores",
    "ci": "CI/CD",
    "build": "Build",
    "revert": "Reverts",
    "breaking": "Breaking Changes",
}

_SECTION_ORDER = [
    "Breaking Changes",
    "Features",
    "Bug Fixes",
    "Performance",
    "Refactoring",
    "Documentation",
    "Tests",
    "CI/CD",
    "Build",
    "Chores",
    "Style",
    "Reverts",
]

_COMMIT_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?\s*:\s*(?P<desc>.+)$",
    re.IGNORECASE,
)

_LOG_SEP = "---COMMIT---"
_LOG_FMT = f"%H{chr(31)}%an{chr(31)}%ai{chr(31)}%B{_LOG_SEP}"


def _run_git(args: list[str], cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=15,
        )
        return proc.stdout
    except Exception:
        return ""


def _parse_commit_block(block: str) -> ConventionalCommit | None:
    """Parse a single commit block (hash\x1fauthor\x1fdate\x1fbody)."""
    parts = block.split(chr(31), 3)
    if len(parts) < 4:
        return None

    hash_, author, date, message = parts
    lines = message.strip().splitlines()
    if not lines:
        return None

    subject = lines[0].strip()
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

    m = _COMMIT_RE.match(subject)
    if not m:
        return None

    is_breaking = bool(m.group("breaking")) or "BREAKING CHANGE" in body

    return ConventionalCommit(
        hash=hash_.strip(),
        type=m.group("type").lower(),
        scope=m.group("scope") or "",
        description=m.group("desc").strip(),
        body=body,
        breaking=is_breaking,
        date=date.strip()[:10],
        author=author.strip(),
        raw_message=message.strip(),
    )


# ---------------------------------------------------------------------------
# ChangelogGenerator
# ---------------------------------------------------------------------------

class ChangelogGenerator:
    """
    Generate a CHANGELOG from git conventional commits.

    Parameters
    ----------
    project_root : str | None
        Root of the git repository.
    since_tag : str | None
        Generate log since this git tag. Defaults to all history.
    until_ref : str
        Generate log up to this ref. Defaults to HEAD.
    version : str
        Version label for the "current" (unreleased) section.
    """

    def __init__(
        self,
        project_root: str | None = None,
        since_tag: str | None = None,
        until_ref: str = "HEAD",
        version: str = "Unreleased",
    ) -> None:
        self._root = str(Path(project_root) if project_root else Path.cwd())
        self._since_tag = since_tag
        self._until_ref = until_ref
        self._version = version

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> ChangelogResult:
        raw_commits = self._fetch_commits()
        commits, unrecognized = self._parse_commits(raw_commits)
        release = self._build_release(commits)
        return ChangelogResult(releases=[release], unrecognized_commits=unrecognized)

    def save(self, result: ChangelogResult, path: str | None = None) -> str:
        """Write CHANGELOG.md and return the path."""
        target = Path(path) if path else Path(self._root) / "CHANGELOG.md"
        content = result.to_markdown()
        target.write_text(content, encoding="utf-8")
        return str(target)

    def get_tags(self) -> list[str]:
        """Return available git tags for --since-tag selection."""
        raw = _run_git(["tag", "--sort=-creatordate"], self._root)
        return [t.strip() for t in raw.splitlines() if t.strip()]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_commits(self) -> list[str]:
        ref_range = self._until_ref
        if self._since_tag:
            ref_range = f"{self._since_tag}..{self._until_ref}"

        raw = _run_git(
            ["log", f"--format={_LOG_FMT}", ref_range],
            self._root,
        )
        return [b.strip() for b in raw.split(_LOG_SEP) if b.strip()]

    def _parse_commits(
        self, blocks: list[str]
    ) -> tuple[list[ConventionalCommit], list[str]]:
        commits = []
        unrecognized = []
        for block in blocks:
            commit = _parse_commit_block(block)
            if commit:
                commits.append(commit)
            else:
                # Extract just the subject for display
                first_line = block.split("\n")[0].split(chr(31))[-1].strip()
                if first_line:
                    unrecognized.append(first_line)
        return commits, unrecognized

    def _build_release(self, commits: list[ConventionalCommit]) -> ChangelogRelease:
        today = datetime.now().strftime("%Y-%m-%d")
        section_map: dict[str, ChangelogSection] = {}

        for title in _SECTION_ORDER:
            section_map[title] = ChangelogSection(title=title)

        for commit in commits:
            if commit.breaking:
                section_map["Breaking Changes"].commits.append(commit)

            title = _TYPE_MAP.get(commit.type)
            if title and title != "Breaking Changes":
                section_map.setdefault(title, ChangelogSection(title=title))
                section_map[title].commits.append(commit)

        sections = [section_map[t] for t in _SECTION_ORDER if t in section_map]
        return ChangelogRelease(
            version=self._version,
            date=today,
            sections=sections,
        )
