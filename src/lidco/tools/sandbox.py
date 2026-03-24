"""ExecutionSandbox — restrict bash commands for safety."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxVerdict:
    allowed: bool
    reason: str


_DEFAULT_BLOCKED: list[str] = [
    r"rm\s+-rf\s+/",
    r"dd\s+if=",
    r":\(\)\s*\{",       # fork bomb
    r"mkfs\b",
    r">(>\s*)?/dev/sd",
    r"chmod\s+777\s+/",
    r"sudo\s+rm\s+-rf",
]


class ExecutionSandbox:
    """Validate bash commands before execution."""

    def __init__(
        self,
        allowed_dirs: list[str] | None = None,
        blocked_patterns: list[str] | None = None,
        allowed_env_vars: list[str] | None = None,
        network_disabled: bool = False,
    ) -> None:
        self._allowed_dirs = allowed_dirs or []
        self._blocked_patterns = [re.compile(p, re.IGNORECASE) for p in (blocked_patterns or _DEFAULT_BLOCKED)]
        self._allowed_env_vars = set(allowed_env_vars or [])
        self._network_disabled = network_disabled

    @property
    def network_disabled(self) -> bool:
        return self._network_disabled

    def add_blocked_pattern(self, pattern: str) -> None:
        self._blocked_patterns.append(re.compile(pattern, re.IGNORECASE))

    def check(self, cmd: str, cwd: str = "") -> SandboxVerdict:
        """Validate a command. Returns SandboxVerdict."""
        # Check blocked patterns
        for pat in self._blocked_patterns:
            if pat.search(cmd):
                return SandboxVerdict(allowed=False, reason=f"blocked pattern: {pat.pattern}")

        # Check working directory restriction
        if self._allowed_dirs and cwd:
            cwd_path = Path(cwd).resolve()
            if not any(str(cwd_path).startswith(d) for d in self._allowed_dirs):
                return SandboxVerdict(allowed=False, reason=f"cwd {cwd} not in allowed_dirs")

        # Check network commands if network disabled
        if self._network_disabled:
            network_cmds = re.compile(r"\b(curl|wget|nc|ncat|ssh|scp|rsync|git\s+push|git\s+pull|pip\s+install|npm\s+install)\b")
            if network_cmds.search(cmd):
                return SandboxVerdict(allowed=False, reason="network access disabled")

        return SandboxVerdict(allowed=True, reason="ok")

    def is_env_var_allowed(self, var: str) -> bool:
        if not self._allowed_env_vars:
            return True  # no restriction
        return var in self._allowed_env_vars
