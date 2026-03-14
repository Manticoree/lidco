"""Sandbox validation for shell command and file write operations.

Defense-in-depth: even if permission was granted, the sandbox enforces
that writes stay within configured writable roots and blocked paths
(like .git/ and .lidco/) are never modified.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from lidco.core.config import SandboxConfig

logger = logging.getLogger(__name__)

# Patterns for output redirection in shell commands (handles quoted paths)
_REDIRECT_RE = re.compile(r"(?:>>?)\s*([\"']?)([^\s;&|\"']+)\1")
_TEE_RE = re.compile(r"\btee\s+([\"']?)([^\s;&|\"']+)\1")
# Patterns for cd command
_CD_RE = re.compile(r"\bcd\s+([^\s;&|]+)")


class SandboxValidator:
    """Validates file paths and commands against sandbox configuration."""

    def __init__(self, config: SandboxConfig, project_dir: Path) -> None:
        self._project_dir = project_dir.resolve()
        self._blocked = list(config.blocked_paths)

        if config.writable_roots:
            self._writable_roots = [
                (project_dir / r).resolve() for r in config.writable_roots
            ]
        else:
            # Default: project directory only
            self._writable_roots = [self._project_dir]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_write_path(self, path: str) -> tuple[bool, str]:
        """Check if a path is writable. Returns (allowed, reason)."""
        try:
            target = Path(path).resolve()
        except Exception:
            return False, f"Invalid path: {path}"

        # Check blocked paths
        for blocked in self._blocked:
            blocked_abs = (self._project_dir / blocked).resolve()
            try:
                target.relative_to(blocked_abs)
                return False, f"Path is inside blocked directory: {blocked}"
            except ValueError:
                pass

        # Check writable roots
        for root in self._writable_roots:
            try:
                target.relative_to(root)
                return True, ""
            except ValueError:
                pass

        return False, (
            f"Path is outside writable roots. "
            f"Writable: {[str(r) for r in self._writable_roots]}"
        )

    # Patterns indicating complex shell constructs that bypass static analysis
    _COMPLEX_SHELL_RE = re.compile(
        r"\$\(|`[^`]+`|\$\{|\bcp\s|\bmv\s|\bpython\s+-c\s|\bperl\s+-e\s|\bnode\s+-e\s|<<\s*['\"]?EOF",
        re.IGNORECASE,
    )

    def validate_command(self, command: str) -> tuple[bool, str]:
        """Check if a shell command targets allowed paths.

        NOTE: This is defense-in-depth validation only. It checks literal
        redirect targets and tee/cd destinations parsed via regex. Complex
        constructs (variable expansion, command substitution, cp/mv, heredocs,
        one-liner interpreters) are NOT blocked — they are logged as warnings.
        The permission engine provides the primary security boundary; sandbox
        adds a secondary check for common redirect patterns.
        """
        # Log complex constructs that bypass static analysis
        if self._COMPLEX_SHELL_RE.search(command):
            logger.warning(
                "Sandbox: complex shell construct in command (static analysis limited): %s",
                command[:200],
            )
        # Check output redirections (>, >>)
        for m in _REDIRECT_RE.finditer(command):
            target = m.group(2).strip()
            if target:
                allowed, reason = self.validate_write_path(target)
                if not allowed:
                    return False, f"Command redirects to blocked path: {reason}"

        # Check tee targets
        for m in _TEE_RE.finditer(command):
            target = m.group(2).strip()
            if target:
                allowed, reason = self.validate_write_path(target)
                if not allowed:
                    return False, f"Command pipes tee to blocked path: {reason}"

        # Check cd targets
        for m in _CD_RE.finditer(command):
            target = m.group(1).strip("'\"")
            try:
                resolved = (self._project_dir / target).resolve()
                # cd outside project dir is suspicious but not blocked by default
                in_project = False
                for root in self._writable_roots:
                    try:
                        resolved.relative_to(root)
                        in_project = True
                        break
                    except ValueError:
                        pass
                if not in_project:
                    logger.debug("cd to path outside writable roots: %s", resolved)
            except Exception:
                pass

        return True, ""

    def is_blocked_path(self, path: str) -> bool:
        """Check if a path resolves inside a blocked directory."""
        allowed, _ = self.validate_write_path(path)
        return not allowed
