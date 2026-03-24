"""SessionDiffCollector — collect all file changes since session start."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileDiff:
    path: str
    diff: str
    additions: int
    deletions: int


@dataclass
class SessionDiff:
    files: list[FileDiff]
    total_additions: int
    total_deletions: int

    @property
    def has_changes(self) -> bool:
        return len(self.files) > 0


class SessionDiffCollector:
    """Collect unified diff of all changes since a git ref."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()
        # In-memory fallback: track changed files manually
        self._tracked_changes: dict[str, tuple[str, str]] = {}  # path -> (original, current)

    def track(self, path: str, original: str, current: str) -> None:
        """Track a file change in-memory fallback."""
        self._tracked_changes[path] = (original, current)

    def collect(self, since_ref: str = "HEAD") -> SessionDiff:
        """Collect all diffs since since_ref (git diff) or from tracked changes."""
        try:
            return self._collect_from_git(since_ref)
        except Exception:
            return self._collect_from_tracked()

    def _collect_from_git(self, since_ref: str) -> SessionDiff:
        result = subprocess.run(
            ["git", "diff", since_ref],
            cwd=self._project_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError("git diff failed")

        return _parse_unified_diff(result.stdout)

    def _collect_from_tracked(self) -> SessionDiff:
        import difflib
        files = []
        for path, (original, current) in self._tracked_changes.items():
            diff_lines = list(difflib.unified_diff(
                original.splitlines(keepends=True),
                current.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            ))
            diff_str = "".join(diff_lines)
            additions = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            deletions = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
            if diff_str:
                files.append(FileDiff(path=path, diff=diff_str, additions=additions, deletions=deletions))

        return SessionDiff(
            files=files,
            total_additions=sum(f.additions for f in files),
            total_deletions=sum(f.deletions for f in files),
        )


def _parse_unified_diff(text: str) -> SessionDiff:
    """Parse a unified diff string into FileDiff objects."""
    files = []
    current_path = ""
    current_lines: list[str] = []

    for line in text.splitlines(keepends=True):
        if line.startswith("diff --git"):
            if current_path and current_lines:
                additions = sum(1 for l in current_lines if l.startswith("+") and not l.startswith("+++"))
                deletions = sum(1 for l in current_lines if l.startswith("-") and not l.startswith("---"))
                files.append(FileDiff(path=current_path, diff="".join(current_lines), additions=additions, deletions=deletions))
            current_path = line.split(" b/")[-1].strip() if " b/" in line else ""
            current_lines = []
        current_lines.append(line)

    if current_path and current_lines:
        additions = sum(1 for l in current_lines if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in current_lines if l.startswith("-") and not l.startswith("---"))
        files.append(FileDiff(path=current_path, diff="".join(current_lines), additions=additions, deletions=deletions))

    return SessionDiff(
        files=files,
        total_additions=sum(f.additions for f in files),
        total_deletions=sum(f.deletions for f in files),
    )
