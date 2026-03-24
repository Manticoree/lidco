"""Worktree-isolated parallel agent runner — each task gets its own git worktree."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable


@dataclass
class WorktreeTask:
    name: str
    prompt: str
    branch: str = ""   # auto-generated if empty


@dataclass
class WorktreeResult:
    task: WorktreeTask
    success: bool
    output: str
    worktree_path: str
    branch: str
    error: str = ""


@dataclass
class ParallelResult:
    results: list[WorktreeResult]
    successful: int
    failed: int

    @property
    def all_success(self) -> bool:
        return self.failed == 0


def _git_available() -> bool:
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _create_worktree(repo_root: str, branch: str, worktree_path: str) -> tuple[bool, str]:
    """Create a git worktree. Returns (success, error_message)."""
    try:
        # Create a new branch + worktree
        r = subprocess.run(
            ["git", "worktree", "add", "-b", branch, worktree_path],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=30,
        )
        if r.returncode != 0:
            # Try without -b (branch may exist already)
            r2 = subprocess.run(
                ["git", "worktree", "add", worktree_path, branch],
                capture_output=True,
                text=True,
                cwd=repo_root,
                timeout=30,
            )
            if r2.returncode != 0:
                return False, r2.stderr
        return True, ""
    except Exception as e:
        return False, str(e)


def _remove_worktree(repo_root: str, worktree_path: str) -> None:
    """Remove a git worktree (prune reference)."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", worktree_path],
            capture_output=True,
            cwd=repo_root,
            timeout=15,
        )
    except Exception:
        pass
    # Also physically remove if still there
    try:
        shutil.rmtree(worktree_path, ignore_errors=True)
    except Exception:
        pass


class WorktreeRunner:
    """Run multiple tasks in parallel, each in an isolated git worktree.

    Each task gets its own branch + working directory copy, so tasks
    don't interfere with each other's file edits.
    """

    def __init__(
        self,
        repo_root: str | Path = ".",
        task_runner: Callable[[WorktreeTask, str], Awaitable[str]] | None = None,
    ) -> None:
        self.repo_root = str(Path(repo_root).resolve())
        self._runner = task_runner

    def _make_branch_name(self, task_name: str, idx: int) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in task_name.lower())
        return f"lidco-parallel-{idx}-{safe[:30]}"

    async def _run_task(self, task: WorktreeTask, idx: int, tmp_dir: str) -> WorktreeResult:
        branch = task.branch or self._make_branch_name(task.name, idx)
        wt_path = str(Path(tmp_dir) / f"wt_{idx}")

        if _git_available():
            ok, err = _create_worktree(self.repo_root, branch, wt_path)
            if not ok:
                # Fall back to tmp copy
                try:
                    shutil.copytree(self.repo_root, wt_path, ignore=shutil.ignore_patterns(".git"))
                except Exception as copy_err:
                    return WorktreeResult(task=task, success=False, output="", worktree_path=wt_path, branch=branch, error=str(copy_err))
        else:
            # No git — use plain copy
            try:
                shutil.copytree(self.repo_root, wt_path, ignore=shutil.ignore_patterns(".git"))
            except Exception as e:
                return WorktreeResult(task=task, success=False, output="", worktree_path=wt_path, branch=branch, error=str(e))

        try:
            if self._runner is not None:
                output = await self._runner(task, wt_path)
            else:
                output = f"[no runner] Task '{task.name}' prepared in {wt_path}"
            return WorktreeResult(task=task, success=True, output=output, worktree_path=wt_path, branch=branch)
        except Exception as e:
            return WorktreeResult(task=task, success=False, output="", worktree_path=wt_path, branch=branch, error=str(e))

    async def run_parallel(self, tasks: list[WorktreeTask]) -> ParallelResult:
        """Run all tasks in parallel worktrees.

        Creates a temporary directory for worktrees and cleans up afterwards.
        """
        with tempfile.TemporaryDirectory(prefix="lidco-wt-") as tmp_dir:
            coros = [self._run_task(t, i, tmp_dir) for i, t in enumerate(tasks)]
            results: list[WorktreeResult] = list(await asyncio.gather(*coros, return_exceptions=False))

        successful = sum(1 for r in results if r.success)
        return ParallelResult(results=results, successful=successful, failed=len(results) - successful)
