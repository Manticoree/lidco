"""Turbo command runner — auto-execute approved commands without per-command confirmation.

Windsurf Turbo mode parity: pre-approved command allowlist lets the agent run
shell commands immediately without asking; blocked commands are denied outright;
everything else requires explicit confirmation (normal mode).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable

# Default safe allowlist patterns (regex)
_DEFAULT_ALLOWED: list[str] = [
    r"^python\b",
    r"^pytest\b",
    r"^pip\b",
    r"^git (status|log|diff|show|branch|fetch)\b",
    r"^ls\b",
    r"^cat\b",
    r"^echo\b",
    r"^ruff\b",
    r"^black\b",
    r"^mypy\b",
    r"^flake8\b",
]

# Default blocked patterns (dangerous commands)
_DEFAULT_BLOCKED: list[str] = [
    r"rm\s+-rf",
    r"sudo\b",
    r"chmod\b",
    r":(){:|:&};:",  # fork bomb
    r"dd\s+if=",
    r"mkfs\b",
    r">\s*/dev/",
]


@dataclass
class RunResult:
    command: str
    stdout: str
    stderr: str
    returncode: int
    approved: bool
    blocked: bool
    dry_run: bool

    @property
    def success(self) -> bool:
        return self.approved and not self.blocked and self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout + self.stderr).strip()


class TurboRunner:
    """Execute shell commands autonomously based on an allowlist/blocklist.

    Parameters
    ----------
    allowed_patterns:
        Regex patterns; matching commands are auto-approved.
    blocked_patterns:
        Regex patterns; matching commands are always denied.
    confirm_callback:
        Called with (command: str) when a command is neither allowed nor blocked.
        Should return True to approve, False to deny.  If None, unmatched commands
        are denied automatically (safest default).
    dry_run:
        If True, no subprocess is spawned; result stdout is "<dry-run>".
    cwd:
        Working directory for subprocesses.
    timeout:
        Per-command timeout in seconds.
    """

    def __init__(
        self,
        allowed_patterns: list[str] | None = None,
        blocked_patterns: list[str] | None = None,
        confirm_callback: Callable[[str], bool] | None = None,
        dry_run: bool = False,
        cwd: str | None = None,
        timeout: int = 60,
    ) -> None:
        self._allowed = [re.compile(p) for p in (allowed_patterns or _DEFAULT_ALLOWED)]
        self._blocked = [re.compile(p) for p in (blocked_patterns or _DEFAULT_BLOCKED)]
        self._confirm = confirm_callback
        self.dry_run = dry_run
        self.cwd = cwd
        self.timeout = timeout
        self._history: list[RunResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, command: str) -> bool:
        """Return True if command matches an allow pattern."""
        return any(p.search(command) for p in self._allowed)

    def is_blocked(self, command: str) -> bool:
        """Return True if command matches a block pattern."""
        return any(p.search(command) for p in self._blocked)

    def add_allowed(self, pattern: str) -> None:
        self._allowed.append(re.compile(pattern))

    def add_blocked(self, pattern: str) -> None:
        self._blocked.append(re.compile(pattern))

    def run(self, command: str) -> RunResult:
        """Decide whether to run *command* and execute it if approved."""
        if self.is_blocked(command):
            result = RunResult(
                command=command,
                stdout="",
                stderr="Command blocked by turbo safety rules.",
                returncode=-1,
                approved=False,
                blocked=True,
                dry_run=self.dry_run,
            )
            self._history.append(result)
            return result

        approved = self.is_allowed(command)
        if not approved:
            if self._confirm is not None:
                approved = self._confirm(command)
            # else: denied (approved stays False)

        if not approved:
            result = RunResult(
                command=command,
                stdout="",
                stderr="Command not in turbo allowlist; denied.",
                returncode=-1,
                approved=False,
                blocked=False,
                dry_run=self.dry_run,
            )
            self._history.append(result)
            return result

        # Execute
        if self.dry_run:
            result = RunResult(
                command=command,
                stdout="<dry-run>",
                stderr="",
                returncode=0,
                approved=True,
                blocked=False,
                dry_run=True,
            )
        else:
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.cwd,
                    timeout=self.timeout,
                )
                result = RunResult(
                    command=command,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    returncode=proc.returncode,
                    approved=True,
                    blocked=False,
                    dry_run=False,
                )
            except subprocess.TimeoutExpired:
                result = RunResult(
                    command=command,
                    stdout="",
                    stderr=f"Command timed out after {self.timeout}s.",
                    returncode=-1,
                    approved=True,
                    blocked=False,
                    dry_run=False,
                )
        self._history.append(result)
        return result

    def run_many(self, commands: list[str]) -> list[RunResult]:
        """Run a sequence of commands; stop on first failure."""
        results: list[RunResult] = []
        for cmd in commands:
            r = self.run(cmd)
            results.append(r)
            if not r.success:
                break
        return results

    @property
    def history(self) -> list[RunResult]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()

    def summary(self) -> dict:
        total = len(self._history)
        succeeded = sum(1 for r in self._history if r.success)
        blocked = sum(1 for r in self._history if r.blocked)
        denied = sum(1 for r in self._history if not r.approved and not r.blocked)
        return {
            "total": total,
            "succeeded": succeeded,
            "blocked": blocked,
            "denied": denied,
            "failed": total - succeeded - blocked - denied,
        }
