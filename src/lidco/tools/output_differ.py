"""Output differ — capture command output and diff before/after states."""

from __future__ import annotations

import difflib
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class DiffResult:
    """Result of diffing two text blobs."""

    added_lines: int
    removed_lines: int
    diff_text: str
    changed: bool


class OutputDiffer:
    """Capture command output and compute unified diffs."""

    def capture(self, command: str, timeout: int = 30) -> str:
        """Run *command* and return its stdout as a string."""
        try:
            proc = subprocess.run(
                command,
                shell=True,  # noqa: S602
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return proc.stdout
        except subprocess.TimeoutExpired:
            return f"<timed out after {timeout}s>"
        except Exception as exc:
            return f"<error: {exc}>"

    def diff(self, before: str, after: str) -> DiffResult:
        """Compute a unified diff between *before* and *after*."""
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile="before",
                tofile="after",
            )
        )

        added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
        diff_text = "".join(diff_lines)
        return DiffResult(
            added_lines=added,
            removed_lines=removed,
            diff_text=diff_text,
            changed=bool(diff_lines),
        )
