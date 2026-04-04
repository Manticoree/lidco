"""CommitValidator — validate commit messages against conventions.

Stdlib only.  No mutation of input data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult:
    """Immutable result of a commit message validation."""

    valid: bool
    issues: List[str] = field(default_factory=list)
    is_conventional: bool = False
    has_breaking: bool = False


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>\w+)"
    r"(?:\((?P<scope>[^)]*)\))?"
    r"(?P<bang>!)?"
    r":\s+"
    r"(?P<description>.+)$",
)

_BREAKING_RE = re.compile(r"BREAKING[\s-]CHANGE", re.IGNORECASE)

# Default allowed types
DEFAULT_TYPES = frozenset(
    ["feat", "fix", "refactor", "docs", "test", "chore", "perf", "ci", "style", "build", "revert"]
)


# ---------------------------------------------------------------------------
# CommitValidator
# ---------------------------------------------------------------------------

class CommitValidator:
    """Validate a commit message string."""

    def __init__(
        self,
        *,
        max_subject_length: int = 72,
        allowed_types: Optional[Sequence[str]] = None,
    ) -> None:
        self._max_subject = max_subject_length
        self._allowed_types: frozenset[str] = (
            frozenset(allowed_types) if allowed_types is not None else DEFAULT_TYPES
        )

    # -- public API -----------------------------------------------------

    def validate(self, message: str) -> ValidationResult:
        """Full validation returning a *ValidationResult*."""
        issues: list[str] = list(self.issues(message))
        is_conv = self.check_conventional(message)
        has_break = self.detect_breaking(message)
        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            is_conventional=is_conv,
            has_breaking=has_break,
        )

    def check_conventional(self, message: str) -> bool:
        """Return *True* if *message* matches conventional-commit format."""
        first_line = message.split("\n", 1)[0]
        m = _CONVENTIONAL_RE.match(first_line)
        if m is None:
            return False
        return m.group("type") in self._allowed_types

    def check_scope(self, message: str, allowed: Sequence[str]) -> bool:
        """Return *True* if the scope (if present) is in *allowed*."""
        first_line = message.split("\n", 1)[0]
        m = _CONVENTIONAL_RE.match(first_line)
        if m is None:
            return False
        scope = m.group("scope")
        if scope is None:
            # No scope is acceptable.
            return True
        return scope in allowed

    def detect_breaking(self, message: str) -> bool:
        """Return *True* if the message signals a breaking change."""
        first_line = message.split("\n", 1)[0]
        m = _CONVENTIONAL_RE.match(first_line)
        if m and m.group("bang"):
            return True
        return bool(_BREAKING_RE.search(message))

    def issues(self, message: str) -> List[str]:
        """Return a list of human-readable issue strings."""
        problems: list[str] = []
        if not message or not message.strip():
            problems.append("Commit message is empty.")
            return problems

        first_line = message.split("\n", 1)[0]

        if len(first_line) > self._max_subject:
            problems.append(
                f"Subject line exceeds {self._max_subject} characters "
                f"({len(first_line)} chars)."
            )

        if first_line[0:1].isupper():
            m = _CONVENTIONAL_RE.match(first_line)
            if m is None:
                problems.append("Subject line starts with uppercase but is not conventional format.")

        if not self.check_conventional(message):
            problems.append("Message does not follow conventional-commit format.")

        m = _CONVENTIONAL_RE.match(first_line)
        if m and m.group("type") not in self._allowed_types:
            problems.append(
                f"Unknown commit type '{m.group('type')}'. "
                f"Allowed: {', '.join(sorted(self._allowed_types))}."
            )

        return problems
