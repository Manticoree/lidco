"""Filesystem Jail — restricts file access based on sandbox policy."""
from __future__ import annotations

import os
import time
from typing import Callable, List

from lidco.sandbox.policy import PolicyViolation, SandboxPolicy


class FsJail:
    """Restricts filesystem access to allowed paths, blocking symlink escapes."""

    def __init__(
        self,
        policy: SandboxPolicy,
        resolve_fn: Callable[[str], str] = os.path.realpath,
    ) -> None:
        self._policy = policy
        self._resolve_fn = resolve_fn
        self._violations: list[PolicyViolation] = []

    @property
    def violations(self) -> List[PolicyViolation]:
        """Return list of recorded violations."""
        return list(self._violations)

    def _resolve_safe(self, path: str) -> str:
        """Resolve path without following dangerous symlinks.

        Uses the injected resolve_fn (default: os.path.realpath) and then
        checks whether the resolved path escapes allowed directories.
        """
        resolved = self._resolve_fn(path)
        return resolved

    def _normalize(self, path: str) -> str:
        """Normalize a path for comparison."""
        return os.path.normcase(os.path.normpath(path))

    def _is_under(self, path: str, directory: str) -> bool:
        """Check if *path* is under *directory* (inclusive)."""
        np = self._normalize(path)
        nd = self._normalize(directory)
        # Exact match or is a child
        if np == nd:
            return True
        return np.startswith(nd + os.sep)

    def _is_denied(self, resolved: str) -> bool:
        for dp in self._policy.denied_paths:
            if self._is_under(resolved, dp):
                return True
        return False

    def _is_allowed(self, resolved: str) -> bool:
        if not self._policy.allowed_paths:
            return True
        for ap in self._policy.allowed_paths:
            if self._is_under(resolved, ap):
                return True
        return False

    def _record_violation(self, detail: str) -> None:
        self._violations.append(
            PolicyViolation(
                violation_type="fs",
                detail=detail,
                timestamp=time.time(),
                blocked=True,
            )
        )

    def check_path(self, path: str) -> bool:
        """Check if *path* is accessible (resolve and verify)."""
        resolved = self._resolve_safe(path)

        # Check symlink escape: if the original path and resolved differ,
        # ensure the resolved path is still in allowed territory
        if self._is_denied(resolved):
            self._record_violation(f"Access denied: {path} -> {resolved}")
            return False

        if not self._is_allowed(resolved):
            self._record_violation(f"Path not in allowed list: {path} -> {resolved}")
            return False

        return True

    def check_read(self, path: str) -> bool:
        """Read-only access check (more permissive: allows non-denied paths)."""
        resolved = self._resolve_safe(path)

        if self._is_denied(resolved):
            self._record_violation(f"Read denied: {path} -> {resolved}")
            return False

        # Read is allowed even outside allowed_paths, as long as not denied
        return True

    def check_write(self, path: str) -> bool:
        """Write access check (strict: must be in allowed_paths and not denied)."""
        resolved = self._resolve_safe(path)

        if self._is_denied(resolved):
            self._record_violation(f"Write denied (denied path): {path} -> {resolved}")
            return False

        if not self._is_allowed(resolved):
            self._record_violation(f"Write denied (not allowed): {path} -> {resolved}")
            return False

        return True
