"""Git Stash Manager — manage git stashes programmatically (stdlib only).

Wraps `git stash` subcommands to list, push, pop, apply, drop, and show
stashes with structured metadata.  All git operations go through subprocess
so no git library dependency is needed.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Any


class StashError(Exception):
    """Raised when a git stash operation fails."""


@dataclass
class StashEntry:
    """Metadata for a single git stash entry."""

    index: int            # stash@{N}
    message: str          # user-provided or auto message
    branch: str           # branch the stash was created on
    ref: str              # e.g. "stash@{0}"
    sha: str = ""         # abbreviated commit hash

    @property
    def name(self) -> str:
        return self.ref

    def __str__(self) -> str:
        return f"{self.ref}: {self.message}"


@dataclass
class StashResult:
    """Result of a stash operation."""

    success: bool
    output: str
    entry: StashEntry | None = None


class StashManager:
    """High-level interface to `git stash` operations.

    Usage::

        mgr = StashManager(repo_path="/path/to/repo")
        result = mgr.push(message="WIP: fixing auth")
        entries = mgr.list()
        mgr.pop()
        mgr.apply("stash@{1}")
        mgr.drop(0)
    """

    def __init__(
        self,
        repo_path: str = ".",
        git_executable: str = "git",
    ) -> None:
        self._root = repo_path
        self._git = git_executable

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _run(self, *args: str, check: bool = False) -> subprocess.CompletedProcess:
        cmd = [self._git, *args]
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self._root,
            )
        except FileNotFoundError as exc:
            raise StashError(f"git executable not found: {self._git}") from exc

    def _check(self, proc: subprocess.CompletedProcess, op: str) -> None:
        if proc.returncode != 0:
            raise StashError(f"{op} failed: {proc.stderr.strip()}")

    def _parse_list(self, output: str) -> list[StashEntry]:
        entries: list[StashEntry] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            # Format: stash@{N}: On branch: message
            m = re.match(r"(stash@\{(\d+)\}):\s*(.*)", line)
            if not m:
                continue
            ref, idx, rest = m.group(1), int(m.group(2)), m.group(3)
            branch_m = re.match(r"On (\S+):\s*(.*)", rest)
            if branch_m:
                branch, message = branch_m.group(1), branch_m.group(2)
            else:
                branch, message = "", rest
            entries.append(StashEntry(index=idx, message=message, branch=branch, ref=ref))
        return entries

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def list(self) -> list[StashEntry]:
        """Return all stash entries, newest first."""
        proc = self._run("stash", "list")
        if proc.returncode != 0:
            return []
        return self._parse_list(proc.stdout)

    def push(
        self,
        message: str = "",
        include_untracked: bool = False,
        paths: list[str] | None = None,
    ) -> StashResult:
        """Stash current changes. Returns result with new entry info."""
        cmd = ["stash", "push"]
        if message:
            cmd += ["-m", message]
        if include_untracked:
            cmd.append("-u")
        if paths:
            cmd.append("--")
            cmd.extend(paths)

        proc = self._run(*cmd)
        if proc.returncode != 0:
            return StashResult(success=False, output=proc.stderr.strip())

        # Fetch the newly created stash entry
        entries = self.list()
        entry = entries[0] if entries else None
        return StashResult(success=True, output=proc.stdout.strip(), entry=entry)

    def pop(self, index: int = 0) -> StashResult:
        """Apply and remove stash@{index}."""
        ref = f"stash@{{{index}}}"
        proc = self._run("stash", "pop", ref)
        if proc.returncode != 0:
            return StashResult(success=False, output=proc.stderr.strip())
        return StashResult(success=True, output=proc.stdout.strip())

    def apply(self, ref: str = "stash@{0}") -> StashResult:
        """Apply stash without removing it."""
        proc = self._run("stash", "apply", ref)
        if proc.returncode != 0:
            return StashResult(success=False, output=proc.stderr.strip())
        return StashResult(success=True, output=proc.stdout.strip())

    def drop(self, index: int = 0) -> StashResult:
        """Remove stash@{index} without applying it."""
        ref = f"stash@{{{index}}}"
        proc = self._run("stash", "drop", ref)
        if proc.returncode != 0:
            return StashResult(success=False, output=proc.stderr.strip())
        return StashResult(success=True, output=proc.stdout.strip())

    def show(self, index: int = 0, stat_only: bool = True) -> str:
        """Return diff or stat for stash@{index}."""
        ref = f"stash@{{{index}}}"
        args = ["stash", "show", ref]
        if stat_only:
            args.append("--stat")
        proc = self._run(*args)
        return proc.stdout.strip() if proc.returncode == 0 else proc.stderr.strip()

    def clear(self) -> StashResult:
        """Remove ALL stash entries. Use with care."""
        proc = self._run("stash", "clear")
        if proc.returncode != 0:
            return StashResult(success=False, output=proc.stderr.strip())
        return StashResult(success=True, output="All stashes cleared.")

    def count(self) -> int:
        return len(self.list())

    def get(self, index: int) -> StashEntry | None:
        entries = self.list()
        return next((e for e in entries if e.index == index), None)

    def summary(self) -> dict[str, Any]:
        entries = self.list()
        return {
            "count": len(entries),
            "stashes": [str(e) for e in entries],
        }
