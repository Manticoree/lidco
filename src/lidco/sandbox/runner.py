"""Sandbox Runner — executes commands within sandbox restrictions."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from lidco.sandbox.fs_jail import FsJail
from lidco.sandbox.net_restrictor import NetworkRestrictor
from lidco.sandbox.policy import PolicyViolation, SandboxPolicy

# Commands that are always blocked
_DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    ":(){ :|:& };:",
    "chmod -R 777 /",
    "format c:",
    "del /f /s /q c:\\",
]


@dataclass
class SandboxResult:
    """Result of a sandboxed command execution."""

    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    violations: List[PolicyViolation] = field(default_factory=list)
    timed_out: bool = False
    allowed: bool = True


class SandboxRunner:
    """Execute commands within sandbox policy restrictions."""

    def __init__(
        self,
        policy: SandboxPolicy,
        fs_jail: FsJail,
        net_restrictor: NetworkRestrictor,
        subprocess_fn: Optional[Callable] = None,
    ) -> None:
        self._policy = policy
        self._fs_jail = fs_jail
        self._net_restrictor = net_restrictor
        self._subprocess_fn = subprocess_fn or self._default_subprocess
        self._violations: list[PolicyViolation] = []

    @staticmethod
    def _default_subprocess(
        command: str,
        cwd: str,
        timeout: int,
    ) -> Tuple[str, str, int, bool]:
        """Default subprocess execution. Returns (stdout, stderr, returncode, timed_out)."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode, False
        except subprocess.TimeoutExpired:
            return "", "Command timed out", -1, True

    def _record_violation(self, vtype: str, detail: str) -> PolicyViolation:
        v = PolicyViolation(
            violation_type=vtype,
            detail=detail,
            timestamp=time.time(),
            blocked=True,
        )
        self._violations.append(v)
        return v

    def check_command(self, command: str) -> Tuple[bool, str]:
        """Pre-check if a command is allowed.

        Returns (allowed, reason).
        """
        cmd_lower = command.strip().lower()

        # Check dangerous patterns
        for pattern in _DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                reason = f"Dangerous command blocked: matches '{pattern}'"
                self._record_violation("proc", reason)
                return False, reason

        # Check subprocess policy
        if not self._policy.allow_subprocesses:
            reason = "Subprocesses not allowed by policy"
            self._record_violation("proc", reason)
            return False, reason

        return True, "ok"

    def run(self, command: str, cwd: str = ".") -> SandboxResult:
        """Execute *command* within sandbox restrictions."""
        violations: list[PolicyViolation] = []

        # Pre-check
        allowed, reason = self.check_command(command)
        if not allowed:
            return SandboxResult(
                stdout="",
                stderr=reason,
                returncode=-1,
                violations=list(self._violations[-1:]),
                timed_out=False,
                allowed=False,
            )

        # Check cwd is accessible
        if not self._fs_jail.check_path(cwd):
            v = self._record_violation("fs", f"cwd not accessible: {cwd}")
            return SandboxResult(
                stdout="",
                stderr=f"Working directory not accessible: {cwd}",
                returncode=-1,
                violations=[v],
                timed_out=False,
                allowed=False,
            )

        # Execute
        stdout, stderr, returncode, timed_out = self._subprocess_fn(
            command, cwd, self._policy.max_time_seconds,
        )

        if timed_out:
            v = self._record_violation(
                "time", f"Command timed out after {self._policy.max_time_seconds}s"
            )
            violations.append(v)

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            violations=violations,
            timed_out=timed_out,
            allowed=True,
        )

    def all_violations(self) -> List[PolicyViolation]:
        """Return all violations from runner, fs_jail, and net_restrictor."""
        all_v: list[PolicyViolation] = []
        all_v.extend(self._violations)
        all_v.extend(self._fs_jail.violations)
        all_v.extend(self._net_restrictor.violations)
        return all_v
