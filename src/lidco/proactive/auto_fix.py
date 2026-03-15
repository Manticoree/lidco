"""Smart auto-fix — Task 412."""

from __future__ import annotations

import asyncio
import difflib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FixResult:
    """Result of an auto-fix operation."""

    file: str
    tool: str
    changes_made: bool
    lines_changed: int
    diff: str = ""


class AutoFixer:
    """Applies automated fixes using ruff, isort, and mypy."""

    _TIMEOUT = 30

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def fix_lint(self, file_path: str, preview: bool = False) -> FixResult:
        """Run `ruff check --fix` on *file_path*.

        If *preview* is True, return a diff without applying changes.
        """
        if not shutil.which("ruff"):
            return FixResult(file=file_path, tool="ruff", changes_made=False, lines_changed=0)

        original = self._read(file_path)

        if preview:
            cmd = ["ruff", "check", "--diff", file_path]
            diff = await self._run(cmd)
            changed = bool(diff.strip())
            return FixResult(
                file=file_path,
                tool="ruff",
                changes_made=changed,
                lines_changed=diff.count("\n-") + diff.count("\n+"),
                diff=diff,
            )

        cmd = ["ruff", "check", "--fix", file_path]
        await self._run(cmd)

        after = self._read(file_path)
        diff = self._make_diff(original, after, file_path)
        return FixResult(
            file=file_path,
            tool="ruff",
            changes_made=original != after,
            lines_changed=max(diff.count("\n-"), diff.count("\n+")),
            diff=diff,
        )

    async def fix_imports(self, file_path: str, preview: bool = False) -> FixResult:
        """Run `isort` on *file_path*."""
        if not shutil.which("isort"):
            return FixResult(file=file_path, tool="isort", changes_made=False, lines_changed=0)

        original = self._read(file_path)

        if preview:
            cmd = ["isort", "--diff", file_path]
            diff = await self._run(cmd)
            changed = bool(diff.strip())
            return FixResult(
                file=file_path,
                tool="isort",
                changes_made=changed,
                lines_changed=diff.count("\n-") + diff.count("\n+"),
                diff=diff,
            )

        cmd = ["isort", file_path]
        await self._run(cmd)

        after = self._read(file_path)
        diff = self._make_diff(original, after, file_path)
        return FixResult(
            file=file_path,
            tool="isort",
            changes_made=original != after,
            lines_changed=max(diff.count("\n-"), diff.count("\n+")),
            diff=diff,
        )

    async def fix_types(self, file_path: str) -> FixResult:
        """Run `mypy` on *file_path* and collect errors (no auto-apply)."""
        if not shutil.which("mypy"):
            return FixResult(file=file_path, tool="mypy", changes_made=False, lines_changed=0)

        cmd = ["mypy", "--no-error-summary", "--show-column-numbers", file_path]
        output = await self._run(cmd)
        has_errors = bool(output.strip())
        return FixResult(
            file=file_path,
            tool="mypy",
            changes_made=False,
            lines_changed=0,
            diff=output,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _run(self, cmd: list[str]) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=self._TIMEOUT)
            return (stdout_b + stderr_b).decode("utf-8", errors="replace")
        except (asyncio.TimeoutError, OSError):
            return ""

    @staticmethod
    def _read(file_path: str) -> str:
        try:
            return Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return ""

    @staticmethod
    def _make_diff(before: str, after: str, file_path: str) -> str:
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        diff = difflib.unified_diff(before_lines, after_lines, fromfile=file_path, tofile=file_path)
        return "".join(diff)
