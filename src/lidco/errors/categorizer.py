"""Q152: Error categorization by pattern matching."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ErrorCategory:
    name: str
    pattern: str
    description: str
    severity: str  # "low" / "medium" / "high" / "critical"


@dataclass
class CategorizedError:
    original: Exception
    category: Optional[ErrorCategory]
    message: str
    timestamp: float


class ErrorCategorizer:
    """Categorize exceptions by matching error messages against regex patterns."""

    def __init__(self) -> None:
        self._categories: list[ErrorCategory] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_category(
        self,
        name: str,
        pattern: str,
        description: str,
        severity: str,
    ) -> None:
        """Register a new category with a regex *pattern*."""
        self._categories.append(
            ErrorCategory(
                name=name,
                pattern=pattern,
                description=description,
                severity=severity,
            )
        )

    def categorize(self, error: Exception) -> CategorizedError:
        """Match *error* against registered categories and return a CategorizedError."""
        msg = str(error)
        err_type = type(error).__name__
        combined = f"{err_type}: {msg}"

        matched: Optional[ErrorCategory] = None
        for cat in self._categories:
            if re.search(cat.pattern, combined, re.IGNORECASE):
                matched = cat
                break

        return CategorizedError(
            original=error,
            category=matched,
            message=msg,
            timestamp=time.time(),
        )

    @property
    def categories(self) -> list[ErrorCategory]:
        """Return a copy of registered categories."""
        return list(self._categories)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def with_defaults(cls) -> "ErrorCategorizer":
        """Return an ErrorCategorizer pre-loaded with common categories."""
        c = cls()
        c.add_category(
            "FileNotFound",
            r"FileNotFoundError|No such file|not found",
            "A required file or path could not be located.",
            "high",
        )
        c.add_category(
            "PermissionError",
            r"PermissionError|Permission denied|Access denied",
            "Insufficient permissions to access a resource.",
            "high",
        )
        c.add_category(
            "ImportError",
            r"ImportError|ModuleNotFoundError|No module named",
            "A Python module or package could not be imported.",
            "medium",
        )
        c.add_category(
            "ValueError",
            r"ValueError|invalid literal|could not convert",
            "An argument or value is invalid.",
            "medium",
        )
        c.add_category(
            "SyntaxError",
            r"SyntaxError|invalid syntax|unexpected EOF",
            "Python source code contains a syntax error.",
            "high",
        )
        c.add_category(
            "ConnectionError",
            r"ConnectionError|ConnectionRefusedError|ConnectionResetError|Connection refused",
            "A network connection could not be established.",
            "critical",
        )
        c.add_category(
            "TimeoutError",
            r"TimeoutError|timed out|deadline exceeded",
            "An operation exceeded its time limit.",
            "critical",
        )
        return c
