"""Review Patterns — Common review feedback patterns and anti-patterns (Q332, task 1772)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    """Severity level for a review pattern."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PatternCategory(Enum):
    """Category of review pattern."""

    ANTI_PATTERN = "anti_pattern"
    BEST_PRACTICE = "best_practice"
    STYLE = "style"
    SECURITY = "security"
    PERFORMANCE = "performance"


@dataclass(frozen=True)
class ReviewPattern:
    """A single review feedback pattern."""

    name: str
    description: str
    category: PatternCategory
    severity: Severity
    languages: tuple[str, ...] = ()
    example_bad: str = ""
    example_good: str = ""
    tags: tuple[str, ...] = ()

    def matches_language(self, language: str) -> bool:
        """Return True if this pattern applies to the given language."""
        if not self.languages:
            return True
        return language.lower() in tuple(l.lower() for l in self.languages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "severity": self.severity.value,
            "languages": list(self.languages),
            "example_bad": self.example_bad,
            "example_good": self.example_good,
            "tags": list(self.tags),
        }


@dataclass
class PatternMatch:
    """A detected pattern match in code."""

    pattern: ReviewPattern
    file_path: str
    line: int
    context: str = ""
    matched_at: float = 0.0

    def __post_init__(self) -> None:
        if self.matched_at == 0.0:
            self.matched_at = time.time()


class PatternRegistry:
    """Registry of known review patterns with search and filtering."""

    def __init__(self) -> None:
        self._patterns: dict[str, ReviewPattern] = {}

    def add(self, pattern: ReviewPattern) -> None:
        """Register a pattern. Overwrites if name already exists."""
        self._patterns = {**self._patterns, pattern.name: pattern}

    def remove(self, name: str) -> bool:
        """Remove a pattern by name. Returns True if removed."""
        if name not in self._patterns:
            return False
        self._patterns = {k: v for k, v in self._patterns.items() if k != name}
        return True

    def get(self, name: str) -> ReviewPattern | None:
        """Look up a pattern by name."""
        return self._patterns.get(name)

    @property
    def count(self) -> int:
        return len(self._patterns)

    def list_all(self) -> list[ReviewPattern]:
        """Return all patterns sorted by name."""
        return sorted(self._patterns.values(), key=lambda p: p.name)

    def find_by_category(self, category: PatternCategory) -> list[ReviewPattern]:
        """Filter patterns by category."""
        return [p for p in self._patterns.values() if p.category == category]

    def find_by_severity(self, severity: Severity) -> list[ReviewPattern]:
        """Filter patterns by severity."""
        return [p for p in self._patterns.values() if p.severity == severity]

    def find_by_language(self, language: str) -> list[ReviewPattern]:
        """Filter patterns applicable to a language."""
        return [p for p in self._patterns.values() if p.matches_language(language)]

    def find_by_tag(self, tag: str) -> list[ReviewPattern]:
        """Filter patterns that contain a given tag."""
        tag_lower = tag.lower()
        return [p for p in self._patterns.values() if tag_lower in tuple(t.lower() for t in p.tags)]

    def search(self, query: str) -> list[ReviewPattern]:
        """Search patterns by name or description substring."""
        q = query.lower()
        return [
            p for p in self._patterns.values()
            if q in p.name.lower() or q in p.description.lower()
        ]


def create_default_registry() -> PatternRegistry:
    """Create a registry pre-loaded with common review patterns."""
    reg = PatternRegistry()
    _defaults = [
        ReviewPattern(
            name="magic-number",
            description="Avoid magic numbers; use named constants",
            category=PatternCategory.BEST_PRACTICE,
            severity=Severity.WARNING,
            example_bad="if retries > 3:",
            example_good="MAX_RETRIES = 3\nif retries > MAX_RETRIES:",
            tags=("readability", "maintainability"),
        ),
        ReviewPattern(
            name="broad-except",
            description="Avoid bare except or catching Exception without re-raising",
            category=PatternCategory.ANTI_PATTERN,
            severity=Severity.ERROR,
            languages=("python",),
            example_bad="except Exception:\n    pass",
            example_good="except ValueError as exc:\n    logger.error(exc)\n    raise",
            tags=("error-handling",),
        ),
        ReviewPattern(
            name="mutation",
            description="Prefer immutable updates over in-place mutation",
            category=PatternCategory.BEST_PRACTICE,
            severity=Severity.WARNING,
            example_bad="obj.field = new_val\nreturn obj",
            example_good="return {**obj, 'field': new_val}",
            tags=("immutability", "functional"),
        ),
        ReviewPattern(
            name="hardcoded-secret",
            description="Never hard-code secrets, tokens, or passwords",
            category=PatternCategory.SECURITY,
            severity=Severity.CRITICAL,
            example_bad='API_KEY = "sk-proj-xxxx"',
            example_good="API_KEY = os.environ['API_KEY']",
            tags=("security", "secrets"),
        ),
        ReviewPattern(
            name="n-plus-one",
            description="Avoid N+1 query patterns; prefer batch or join",
            category=PatternCategory.PERFORMANCE,
            severity=Severity.ERROR,
            example_bad="for user in users:\n    db.query(user.id)",
            example_good="db.query_batch([u.id for u in users])",
            tags=("performance", "database"),
        ),
        ReviewPattern(
            name="console-log",
            description="Remove console.log / print debug statements before merge",
            category=PatternCategory.STYLE,
            severity=Severity.INFO,
            languages=("javascript", "typescript", "python"),
            example_bad="console.log('debug', data)",
            example_good="logger.debug('data: %s', data)",
            tags=("cleanup", "logging"),
        ),
    ]
    for p in _defaults:
        reg.add(p)
    return reg
