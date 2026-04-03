"""GitActionsProvider — simulated git operations."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GitAction:
    """A git action specification."""

    action: str
    target: str
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GitActionResult:
    """Result of a git action."""

    action: str
    success: bool
    message: str
    command: str = ""


class GitActionsProvider:
    """Simulate git operations and keep an action log."""

    def __init__(self) -> None:
        self._log: list[GitActionResult] = []

    def stage(self, paths: list[str]) -> GitActionResult:
        """Simulate staging *paths*."""
        cmd = f"git add {' '.join(paths)}"
        result = GitActionResult(
            action="stage", success=True,
            message=f"Staged {len(paths)} file(s)", command=cmd,
        )
        self._log.append(result)
        return result

    def unstage(self, paths: list[str]) -> GitActionResult:
        """Simulate unstaging *paths*."""
        cmd = f"git restore --staged {' '.join(paths)}"
        result = GitActionResult(
            action="unstage", success=True,
            message=f"Unstaged {len(paths)} file(s)", command=cmd,
        )
        self._log.append(result)
        return result

    def commit(self, message: str) -> GitActionResult:
        """Simulate a commit with *message*."""
        cmd = f'git commit -m "{message}"'
        result = GitActionResult(
            action="commit", success=True,
            message=f"Committed: {message}", command=cmd,
        )
        self._log.append(result)
        return result

    def push(self, remote: str = "origin", branch: str = "") -> GitActionResult:
        """Simulate push to *remote*/*branch*."""
        branch_part = f" {branch}" if branch else ""
        cmd = f"git push {remote}{branch_part}"
        result = GitActionResult(
            action="push", success=True,
            message=f"Pushed to {remote}{branch_part}", command=cmd,
        )
        self._log.append(result)
        return result

    def create_branch(self, name: str) -> GitActionResult:
        """Simulate branch creation."""
        cmd = f"git checkout -b {name}"
        result = GitActionResult(
            action="create_branch", success=True,
            message=f"Created branch '{name}'", command=cmd,
        )
        self._log.append(result)
        return result

    def stash(self, message: str = "") -> GitActionResult:
        """Simulate git stash."""
        cmd = f'git stash push -m "{message}"' if message else "git stash"
        result = GitActionResult(
            action="stash", success=True,
            message=f"Stashed changes" + (f": {message}" if message else ""),
            command=cmd,
        )
        self._log.append(result)
        return result

    def stash_pop(self) -> GitActionResult:
        """Simulate git stash pop."""
        result = GitActionResult(
            action="stash_pop", success=True,
            message="Popped stash", command="git stash pop",
        )
        self._log.append(result)
        return result

    def history(self) -> list[GitActionResult]:
        """Return the action log."""
        return list(self._log)

    def summary(self) -> dict:
        """Return a summary dict."""
        return {
            "total_actions": len(self._log),
            "action_types": list({r.action for r in self._log}),
        }
