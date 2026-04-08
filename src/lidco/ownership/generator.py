"""
CODEOWNERS Generator — generate CODEOWNERS from git blame data.

Supports team mapping, directory rules, review requirements, and export
to GitHub-compatible CODEOWNERS format.  Pure stdlib, no external deps.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BlameEntry:
    """A single blame record for a file."""

    file_path: str
    author: str
    lines: int


@dataclass(frozen=True)
class DirectoryRule:
    """A directory-level ownership rule."""

    pattern: str
    owners: list[str]
    min_reviewers: int = 1


@dataclass(frozen=True)
class CodeownersEntry:
    """One line in a CODEOWNERS file."""

    pattern: str
    owners: list[str]
    min_reviewers: int = 1

    def to_line(self) -> str:
        """Render as a CODEOWNERS line."""
        owners_str = " ".join(self.owners)
        return f"{self.pattern} {owners_str}"


@dataclass
class CodeownersResult:
    """Aggregate result of CODEOWNERS generation."""

    entries: list[CodeownersEntry] = field(default_factory=list)
    unmapped_authors: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Render the full CODEOWNERS file content."""
        lines = ["# Auto-generated CODEOWNERS", "#"]
        for entry in self.entries:
            lines.append(entry.to_line())
        return "\n".join(lines) + "\n"


class CodeownersGenerator:
    """Generate CODEOWNERS from git blame, team mappings and directory rules."""

    def __init__(self) -> None:
        self._team_mapping: dict[str, str] = {}
        self._directory_rules: list[DirectoryRule] = []
        self._min_line_fraction: float = 0.1

    def set_team_mapping(self, mapping: dict[str, str]) -> CodeownersGenerator:
        """Set author-to-team mapping. Returns a new-ish ref for chaining."""
        return CodeownersGenerator._with_updates(
            self, team_mapping=dict(mapping),
        )

    def add_directory_rule(self, rule: DirectoryRule) -> CodeownersGenerator:
        """Add a directory ownership rule. Returns new instance."""
        return CodeownersGenerator._with_updates(
            self, directory_rules=[*self._directory_rules, rule],
        )

    def set_min_line_fraction(self, fraction: float) -> CodeownersGenerator:
        """Set the minimum fraction of lines to be considered an owner."""
        return CodeownersGenerator._with_updates(
            self, min_line_fraction=fraction,
        )

    @staticmethod
    def _with_updates(
        base: CodeownersGenerator,
        team_mapping: dict[str, str] | None = None,
        directory_rules: list[DirectoryRule] | None = None,
        min_line_fraction: float | None = None,
    ) -> CodeownersGenerator:
        gen = CodeownersGenerator()
        gen._team_mapping = team_mapping if team_mapping is not None else dict(base._team_mapping)
        gen._directory_rules = (
            list(directory_rules) if directory_rules is not None else list(base._directory_rules)
        )
        gen._min_line_fraction = (
            min_line_fraction if min_line_fraction is not None else base._min_line_fraction
        )
        return gen

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate(self, blame_entries: list[BlameEntry]) -> CodeownersResult:
        """Generate CODEOWNERS entries from blame data + rules."""
        entries: list[CodeownersEntry] = []
        unmapped: set[str] = set()

        # Group blame by directory prefix
        dir_totals: dict[str, dict[str, int]] = {}
        for be in blame_entries:
            parent = str(Path(be.file_path).parent)
            if parent not in dir_totals:
                dir_totals[parent] = {}
            dir_totals[parent][be.author] = (
                dir_totals[parent].get(be.author, 0) + be.lines
            )

        # Apply directory rules first (explicit rules take precedence)
        covered_patterns: set[str] = set()
        for rule in self._directory_rules:
            entries.append(
                CodeownersEntry(
                    pattern=rule.pattern,
                    owners=list(rule.owners),
                    min_reviewers=rule.min_reviewers,
                )
            )
            covered_patterns.add(rule.pattern.rstrip("/"))

        # Derive ownership from blame data
        for directory, author_lines in sorted(dir_totals.items()):
            norm_dir = directory.replace("\\", "/")
            pattern = f"/{norm_dir}/" if norm_dir != "." else "/"
            if pattern.rstrip("/") in covered_patterns:
                continue

            total_lines = sum(author_lines.values())
            if total_lines == 0:
                continue

            owners: list[str] = []
            for author, lines in sorted(
                author_lines.items(), key=lambda x: x[1], reverse=True
            ):
                if lines / total_lines < self._min_line_fraction:
                    continue
                team = self._team_mapping.get(author)
                if team:
                    owner_label = f"@{team}"
                else:
                    owner_label = f"@{author}"
                    unmapped.add(author)
                if owner_label not in owners:
                    owners.append(owner_label)

            if owners:
                entries.append(CodeownersEntry(pattern=pattern, owners=owners))

        return CodeownersResult(
            entries=entries,
            unmapped_authors=sorted(unmapped),
        )

    def generate_from_git(self, repo_path: str, files: list[str] | None = None) -> CodeownersResult:
        """Run ``git blame`` on *files* (or all tracked files) and generate."""
        tracked = files or self._list_tracked_files(repo_path)
        blame_entries = []
        for fpath in tracked:
            entries = self._blame_file(repo_path, fpath)
            blame_entries.extend(entries)
        return self.generate(blame_entries)

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _list_tracked_files(repo_path: str) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=30,
            )
            return [l for l in result.stdout.strip().splitlines() if l]
        except (subprocess.SubprocessError, FileNotFoundError):
            return []

    @staticmethod
    def _blame_file(repo_path: str, file_path: str) -> list[BlameEntry]:
        try:
            result = subprocess.run(
                ["git", "blame", "--line-porcelain", file_path],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=30,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return []

        author_lines: dict[str, int] = {}
        current_author: str | None = None
        for line in result.stdout.splitlines():
            if line.startswith("author "):
                current_author = line[7:].strip()
            elif line.startswith("\t") and current_author:
                author_lines[current_author] = author_lines.get(current_author, 0) + 1
                current_author = None

        return [
            BlameEntry(file_path=file_path, author=author, lines=count)
            for author, count in author_lines.items()
        ]
