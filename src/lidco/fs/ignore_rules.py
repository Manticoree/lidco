"""Q132: .gitignore-style ignore rule matching."""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass


@dataclass
class IgnoreRule:
    pattern: str
    negated: bool = False


class IgnoreRules:
    """Parse and apply .gitignore-style ignore rules."""

    def __init__(self, patterns: list[str] | None = None) -> None:
        self._rules: list[IgnoreRule] = []
        if patterns:
            for p in patterns:
                self.add(p)

    def add(self, pattern: str) -> None:
        """Add a single pattern line."""
        stripped = pattern.strip()
        if not stripped or stripped.startswith("#"):
            return
        negated = stripped.startswith("!")
        if negated:
            stripped = stripped[1:]
        self._rules.append(IgnoreRule(pattern=stripped, negated=negated))

    def load_gitignore(self, content: str) -> None:
        """Parse a .gitignore file content."""
        for line in content.splitlines():
            self.add(line)

    def is_ignored(self, path: str) -> bool:
        """Return True if *path* is matched by a non-negated rule."""
        norm = path.replace("\\", "/")
        name = os.path.basename(norm)
        ignored = False
        for rule in self._rules:
            pat = rule.pattern
            if self._matches(norm, name, pat):
                ignored = not rule.negated
        return ignored

    def filter(self, paths: list[str]) -> list[str]:
        """Return only the non-ignored paths."""
        return [p for p in paths if not self.is_ignored(p)]

    def __len__(self) -> int:
        return len(self._rules)

    # --- internals -----------------------------------------------------------

    def _matches(self, norm: str, name: str, pattern: str) -> bool:
        # Strip trailing slash (directory marker)
        pat = pattern.rstrip("/")

        # Pattern with slash: match full path
        if "/" in pat:
            return fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(norm, f"*/{pat}")

        # No slash: match basename or any component
        if fnmatch.fnmatch(name, pat):
            return True
        # Also check each path component
        for part in norm.split("/"):
            if fnmatch.fnmatch(part, pat):
                return True
        return False
