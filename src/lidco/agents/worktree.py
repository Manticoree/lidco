"""Git worktree isolation for parallel agents — Task 269.

Each agent running with ``isolation: worktree`` gets a private git worktree
in ``.lidco/worktrees/<agent_id>/``.  On completion:
- If no changes were made → worktree is removed automatically (cleanup).
- If changes exist → path and branch are returned for review/merge.

Usage::

    mgr = WorktreeManager(project_dir)
    path = mgr.create("agent-abc123")       # git worktree add …
    # … agent works in path …
    branch = mgr.finish("agent-abc123")     # cleanup or return branch name
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_WORKTREE_BASE = ".lidco/worktrees"
_BRANCH_PREFIX = "lidco/"


@dataclass
class WorktreeInfo:
    """Metadata for an active worktree."""
    agent_id: str
    path: Path
    branch: str


class WorktreeManager:
    """Manages git worktrees for isolated agent execution.

    Args:
        project_dir: Repository root (must be a git repo).
    """

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir
        self._active: dict[str, WorktreeInfo] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def create(self, agent_id: str) -> Path | None:
        """Create a new worktree for *agent_id*.

        Returns the worktree path on success, or ``None`` if git is unavailable
        or the repo is not clean enough to create a worktree.
        """
        worktree_path = self._project_dir / _WORKTREE_BASE / agent_id
        branch = f"{_BRANCH_PREFIX}{agent_id}"

        try:
            worktree_path.parent.mkdir(parents=True, exist_ok=True)
            self._git(
                "worktree", "add", str(worktree_path), "-b", branch,
                "--no-track",
            )
        except subprocess.CalledProcessError as exc:
            logger.warning("WorktreeManager: failed to create worktree for '%s': %s", agent_id, exc)
            return None
        except FileNotFoundError:
            logger.warning("WorktreeManager: git not found")
            return None

        info = WorktreeInfo(agent_id=agent_id, path=worktree_path, branch=branch)
        self._active[agent_id] = info
        logger.info("WorktreeManager: created worktree '%s' at %s", agent_id, worktree_path)
        return worktree_path

    def has_changes(self, worktree_path: Path) -> bool:
        """Return True if *worktree_path* has uncommitted changes."""
        try:
            result = self._git_output(
                "-C", str(worktree_path), "status", "--porcelain",
            )
            return bool(result.strip())
        except Exception:
            return False

    def finish(self, agent_id: str) -> str | None:
        """Clean up worktree after agent completes.

        * If no changes → removes worktree + branch, returns ``None``.
        * If changes exist → removes worktree metadata but **keeps the branch**;
          returns the branch name for the caller to review/merge.
        """
        info = self._active.pop(agent_id, None)
        if info is None:
            return None

        changed = self.has_changes(info.path)

        try:
            self._git("worktree", "remove", str(info.path), "--force")
        except Exception as exc:
            logger.debug("WorktreeManager: worktree remove failed for '%s': %s", agent_id, exc)

        if changed:
            logger.info(
                "WorktreeManager: agent '%s' left changes on branch '%s'",
                agent_id, info.branch,
            )
            return info.branch

        # No changes — delete the branch too
        try:
            self._git("branch", "-D", info.branch)
        except Exception:
            pass
        return None

    def remove(self, agent_id: str) -> None:
        """Force-remove a worktree without checking for changes."""
        info = self._active.pop(agent_id, None)
        if info is None:
            return
        try:
            self._git("worktree", "remove", str(info.path), "--force")
        except Exception:
            pass
        try:
            self._git("branch", "-D", info.branch)
        except Exception:
            pass

    def list_active(self) -> dict[str, WorktreeInfo]:
        """Return a copy of all active worktree infos."""
        return dict(self._active)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=self._project_dir,
            capture_output=True,
            check=True,
        )

    def _git_output(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self._project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
