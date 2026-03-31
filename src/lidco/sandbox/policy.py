"""Sandbox Policy Engine — defines security policies for sandboxed execution."""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class PolicyViolation:
    """Record of a policy violation."""

    violation_type: str  # fs / net / mem / time / proc
    detail: str
    timestamp: float = 0.0
    blocked: bool = True

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            object.__setattr__(self, "timestamp", time.time())


@dataclass
class SandboxPolicy:
    """Security policy for sandboxed execution."""

    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    deny_all_network: bool = True
    max_memory_mb: int = 512
    max_time_seconds: int = 60
    allow_subprocesses: bool = False

    @classmethod
    def with_defaults(cls) -> SandboxPolicy:
        """Create a policy with sensible defaults.

        Allows cwd, denies system directories.
        """
        cwd = os.getcwd()
        denied: list[str] = []
        if sys.platform == "win32":
            denied.extend([
                "C:\\Windows",
                "C:\\Program Files",
                "C:\\Program Files (x86)",
            ])
        else:
            denied.extend([
                "/etc",
                "/var",
                "/usr",
                "/bin",
                "/sbin",
                "/boot",
                "/proc",
                "/sys",
            ])
        return cls(
            allowed_paths=[cwd],
            denied_paths=denied,
            allowed_domains=[],
            deny_all_network=True,
            max_memory_mb=512,
            max_time_seconds=60,
            allow_subprocesses=False,
        )

    def merge(self, other: SandboxPolicy) -> SandboxPolicy:
        """Merge two policies. Deny wins over allow."""
        # Combine denied paths (union)
        merged_denied = list(set(self.denied_paths) | set(other.denied_paths))

        # Allowed paths: intersection minus anything denied
        merged_allowed = list(
            (set(self.allowed_paths) | set(other.allowed_paths))
        )

        # Allowed domains: intersection-ish — only keep if in both,
        # unless one side is empty (permissive)
        if self.allowed_domains and other.allowed_domains:
            merged_domains = list(
                set(self.allowed_domains) & set(other.allowed_domains)
            )
        elif self.allowed_domains:
            merged_domains = list(self.allowed_domains)
        elif other.allowed_domains:
            merged_domains = list(other.allowed_domains)
        else:
            merged_domains = []

        return SandboxPolicy(
            allowed_paths=merged_allowed,
            denied_paths=merged_denied,
            allowed_domains=merged_domains,
            # Deny wins
            deny_all_network=self.deny_all_network or other.deny_all_network,
            # Stricter limit wins
            max_memory_mb=min(self.max_memory_mb, other.max_memory_mb),
            max_time_seconds=min(self.max_time_seconds, other.max_time_seconds),
            # Deny wins (False is more restrictive)
            allow_subprocesses=self.allow_subprocesses and other.allow_subprocesses,
        )
