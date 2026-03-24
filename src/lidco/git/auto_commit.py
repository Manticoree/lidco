"""Auto-commit mode — stage and commit dirty files after each agent execution."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AutoCommitResult:
    committed: bool
    commit_hash: str | None
    message: str
    files_staged: list[str]


class AutoCommitter:
    """Stage and commit dirty files after each agent execution."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self.project_dir = project_dir or Path.cwd()
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def toggle(self) -> bool:
        """Toggle enabled state; return new state."""
        self._enabled = not self._enabled
        return self._enabled

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            list(args),
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

    def get_dirty_files(self) -> list[str]:
        """Return list of modified/untracked files."""
        result = self._run("git", "status", "--porcelain")
        files = []
        for line in result.stdout.splitlines():
            if line.strip():
                files.append(line[3:].strip())
        return files

    def commit_if_dirty(self, description: str) -> AutoCommitResult:
        """Stage all dirty files and commit. Returns result with commit hash or None."""
        if not self._enabled:
            return AutoCommitResult(committed=False, commit_hash=None, message="auto-commit disabled", files_staged=[])

        dirty = self.get_dirty_files()
        if not dirty:
            return AutoCommitResult(committed=False, commit_hash=None, message="nothing to commit", files_staged=[])

        # Stage all
        self._run("git", "add", "-A")

        # Build commit message
        msg = description if len(description) <= 72 else description[:69] + "..."

        result = self._run("git", "commit", "-m", msg)
        if result.returncode != 0:
            return AutoCommitResult(committed=False, commit_hash=None, message=result.stderr.strip(), files_staged=dirty)

        # Get commit hash
        hash_result = self._run("git", "rev-parse", "--short", "HEAD")
        commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else None

        return AutoCommitResult(committed=True, commit_hash=commit_hash, message=msg, files_staged=dirty)
