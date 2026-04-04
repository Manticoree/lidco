"""Error classification with confidence scoring."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ErrorClassification:
    """Result of classifying an error."""

    type: str  # syntax/runtime/network/permission/resource/timeout/unknown
    confidence: float  # 0.0 – 1.0
    indicators: list[str]
    suggestion: str = ""


_DEFAULT_PATTERNS: dict[str, list[str]] = {
    "syntax": [
        r"SyntaxError",
        r"IndentationError",
        r"TabError",
        r"invalid syntax",
        r"unexpected EOF",
        r"unexpected indent",
        r"expected ':'",
        r"unmatched",
    ],
    "runtime": [
        r"TypeError",
        r"ValueError",
        r"AttributeError",
        r"KeyError",
        r"IndexError",
        r"NameError",
        r"ZeroDivisionError",
        r"ImportError",
        r"ModuleNotFoundError",
        r"RecursionError",
        r"StopIteration",
    ],
    "network": [
        r"ConnectionError",
        r"ConnectionRefusedError",
        r"ConnectionResetError",
        r"TimeoutError.*connect",
        r"socket\.error",
        r"URLError",
        r"HTTPError",
        r"ECONNREFUSED",
        r"ECONNRESET",
        r"DNS",
        r"getaddrinfo",
    ],
    "permission": [
        r"PermissionError",
        r"EACCES",
        r"Access denied",
        r"Permission denied",
        r"Operation not permitted",
        r"EPERM",
        r"Forbidden",
        r"403",
    ],
    "resource": [
        r"MemoryError",
        r"OSError.*No space",
        r"disk quota",
        r"ENOMEM",
        r"ENOSPC",
        r"Too many open files",
        r"EMFILE",
        r"ResourceWarning",
        r"out of memory",
    ],
    "timeout": [
        r"TimeoutError",
        r"timed out",
        r"deadline exceeded",
        r"ETIMEDOUT",
        r"timeout expired",
        r"read timed out",
    ],
}

_SUGGESTIONS: dict[str, str] = {
    "syntax": "Check for missing colons, unmatched brackets, or incorrect indentation.",
    "runtime": "Verify variable types, check None values, and validate function arguments.",
    "network": "Check network connectivity, verify the remote host, and retry the request.",
    "permission": "Check file/directory permissions and ensure sufficient privileges.",
    "resource": "Free up system resources (memory/disk) or increase limits.",
    "timeout": "Increase the timeout value or optimize the operation for speed.",
    "unknown": "Inspect the full traceback for more context.",
}


class ErrorClassifier:
    """Classify errors by type with confidence scoring."""

    def __init__(self) -> None:
        self._patterns: dict[str, list[str]] = {
            k: list(v) for k, v in _DEFAULT_PATTERNS.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self, error_message: str, traceback: str = ""
    ) -> ErrorClassification:
        """Classify *error_message* (optionally with *traceback*)."""
        combined = f"{error_message} {traceback}"
        scores: dict[str, list[str]] = {}
        for etype, pats in self._patterns.items():
            matched: list[str] = []
            for pat in pats:
                if re.search(pat, combined, re.IGNORECASE):
                    matched.append(pat)
            if matched:
                scores[etype] = matched

        if not scores:
            return ErrorClassification(
                type="unknown",
                confidence=0.0,
                indicators=[],
                suggestion=_SUGGESTIONS["unknown"],
            )

        best_type = max(scores, key=lambda t: len(scores[t]))
        indicators = scores[best_type]
        confidence = min(1.0, len(indicators) / 3.0)
        return ErrorClassification(
            type=best_type,
            confidence=round(confidence, 2),
            indicators=indicators,
            suggestion=_SUGGESTIONS.get(best_type, ""),
        )

    def classify_exception(
        self, exc_type: str, message: str
    ) -> ErrorClassification:
        """Classify from an exception type name and message."""
        return self.classify(f"{exc_type}: {message}")

    def add_pattern(self, error_type: str, pattern: str) -> None:
        """Register an additional regex *pattern* for *error_type*."""
        self._patterns.setdefault(error_type, []).append(pattern)

    @property
    def patterns(self) -> dict[str, list[str]]:
        """Return a copy of the current pattern map."""
        return {k: list(v) for k, v in self._patterns.items()}

    def summary(self) -> dict:
        """Return summary statistics."""
        return {
            "error_types": list(self._patterns.keys()),
            "total_patterns": sum(len(v) for v in self._patterns.values()),
        }
