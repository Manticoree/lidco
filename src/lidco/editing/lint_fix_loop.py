# src/lidco/editing/lint_fix_loop.py
"""Auto lint-fix loop: run linter, apply fixes, repeat until clean or max iterations."""

from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class LintIssue:
    """A single lint diagnostic."""

    file: str
    line: int
    col: int
    code: str
    message: str


@dataclass
class LintResult:
    """Lint results for a single file."""

    file: str
    errors: list[LintIssue] = field(default_factory=list)
    clean: bool = True


@dataclass
class FixLoopReport:
    """Summary of a complete lint-fix loop run."""

    iterations: int
    initial_errors: int
    final_errors: int
    files_fixed: list[str] = field(default_factory=list)
    fully_clean: bool = False


# Pattern: path:line:col: CODE message
_LINT_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+):\s+(?P<code>[A-Z]\w*\d*)\s+(?P<message>.+)$"
)

_LINTER_MAP: dict[str, list[str]] = {
    ".py": ["ruff", "check", "--select=E,F,W", "--output-format=concise"],
    ".js": ["eslint", "--format=compact"],
    ".jsx": ["eslint", "--format=compact"],
    ".ts": ["eslint", "--format=compact"],
    ".tsx": ["eslint", "--format=compact"],
    ".go": ["golangci-lint", "run"],
}


class LintFixLoop:
    """Run linter, apply AI/rule fixes, re-lint until clean or max iterations."""

    def __init__(
        self,
        linter_cmd: list[str] | None = None,
        fix_fn: Callable | None = None,
        max_iterations: int = 3,
        timeout: float = 15.0,
    ) -> None:
        self._linter_cmd = linter_cmd
        self._fix_fn = fix_fn
        self._max_iterations = max_iterations
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_lint(self, files: list[str]) -> list[LintResult]:
        """Run linter on *files*.  Returns structured results.

        If the linter binary is not found or times out, returns ``[]``
        (graceful skip).
        """
        if not files:
            return []

        cmd = self._linter_cmd
        if cmd is None:
            cmd = self._detect_linter(files[0])
        if not cmd:
            return []

        full_cmd = list(cmd) + list(files)
        try:
            proc = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except FileNotFoundError:
            return []
        except subprocess.TimeoutExpired:
            return []

        return self.parse_lint_output(proc.stdout, files)

    async def fix_loop(self, files: list[str]) -> FixLoopReport:
        """Main loop: lint -> fix -> re-lint, up to *max_iterations*."""
        if not files:
            return FixLoopReport(
                iterations=0,
                initial_errors=0,
                final_errors=0,
                files_fixed=[],
                fully_clean=True,
            )

        files_fixed_set: set[str] = set()
        initial_errors: int | None = None
        current_errors = 0
        iteration = 0

        for iteration in range(1, self._max_iterations + 1):
            results = self.run_lint(files)

            # Count errors across all results
            error_count = sum(len(r.errors) for r in results)
            if initial_errors is None:
                initial_errors = error_count
            current_errors = error_count

            # If clean, we are done
            if error_count == 0:
                return FixLoopReport(
                    iterations=iteration,
                    initial_errors=initial_errors,
                    final_errors=0,
                    files_fixed=sorted(files_fixed_set),
                    fully_clean=True,
                )

            # No fix function — nothing we can do
            if self._fix_fn is None:
                break

            # Attempt fixes
            for result in results:
                if result.clean:
                    continue
                fixed_content = await self._call_fix_fn(result.file, result.errors)
                if fixed_content is not None:
                    try:
                        with open(result.file, "w", encoding="utf-8") as fh:
                            fh.write(fixed_content)
                        files_fixed_set.add(result.file)
                    except OSError:
                        pass  # graceful — continue loop

        if initial_errors is None:
            initial_errors = 0

        return FixLoopReport(
            iterations=iteration,
            initial_errors=initial_errors,
            final_errors=current_errors,
            files_fixed=sorted(files_fixed_set),
            fully_clean=(current_errors == 0),
        )

    def parse_lint_output(
        self, raw: str, requested_files: list[str]
    ) -> list[LintResult]:
        """Parse ruff/flake8 concise output into structured :class:`LintResult` list.

        Format expected per line::

            path/file.py:line:col: CODE message

        Only issues for *requested_files* are included.  Files with no issues
        are returned as clean.
        """
        issues_by_file: dict[str, list[LintIssue]] = {}
        requested_set = set(requested_files)

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            m = _LINT_LINE_RE.match(line)
            if m is None:
                continue
            file_path = m.group("file")
            if file_path not in requested_set:
                continue
            issue = LintIssue(
                file=file_path,
                line=int(m.group("line")),
                col=int(m.group("col")),
                code=m.group("code"),
                message=m.group("message"),
            )
            issues_by_file.setdefault(file_path, []).append(issue)

        results: list[LintResult] = []
        for f in requested_files:
            errors = issues_by_file.get(f, [])
            results.append(
                LintResult(file=f, errors=errors, clean=(len(errors) == 0))
            )
        return results

    def _detect_linter(self, file_path: str) -> list[str]:
        """Auto-detect linter command by file extension."""
        ext = Path(file_path).suffix.lower()
        return list(_LINTER_MAP.get(ext, []))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_fix_fn(
        self, file: str, errors: list[LintIssue]
    ) -> str | None:
        """Call fix_fn, handling both sync and async callables."""
        if self._fix_fn is None:
            return None
        if asyncio.iscoroutinefunction(self._fix_fn):
            return await self._fix_fn(file, errors)
        return self._fix_fn(file, errors)
