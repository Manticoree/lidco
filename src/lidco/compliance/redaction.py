"""Redact sensitive data with configurable patterns and reversible mapping."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RedactionResult:
    """Result of a redaction operation."""

    text: str
    redacted_count: int
    redacted_types: list[str]


# Built-in PII patterns for redaction
_BUILTIN_PATTERNS: dict[str, str] = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}",
    "phone": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "api_key": r"(?:api[_-]?key|token|secret)[\"':\s=]+[A-Za-z0-9_\-]{16,}",
}


class RedactionEngine:
    """Redact sensitive data from text."""

    def __init__(self, redaction_key: str = "default") -> None:
        self._key = redaction_key
        self._patterns: dict[str, re.Pattern[str]] = {}
        for name, pat in _BUILTIN_PATTERNS.items():
            self._patterns[name] = re.compile(pat)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def redact(
        self, text: str, patterns: list[str] | None = None
    ) -> RedactionResult:
        """Redact matches, replacing with [REDACTED:type]."""
        use_patterns = (
            {k: v for k, v in self._patterns.items() if k in patterns}
            if patterns
            else self._patterns
        )
        result_text = text
        count = 0
        types_found: set[str] = set()
        for name, pattern in use_patterns.items():
            matches = list(pattern.finditer(result_text))
            if matches:
                types_found.add(name)
                count += len(matches)
                result_text = pattern.sub(f"[REDACTED:{name}]", result_text)
        return RedactionResult(
            text=result_text,
            redacted_count=count,
            redacted_types=sorted(types_found),
        )

    def redact_pii(self, text: str) -> RedactionResult:
        """Redact all built-in PII patterns."""
        return self.redact(text)

    def add_pattern(self, name: str, regex: str) -> None:
        """Add or replace a redaction pattern."""
        self._patterns[name] = re.compile(regex)

    def restore(self, redacted_text: str, mapping: dict[str, str]) -> str:
        """Restore redacted text using a mapping of placeholder->original."""
        result = redacted_text
        for placeholder, original in mapping.items():
            result = result.replace(placeholder, original)
        return result

    def create_mapping(self, text: str) -> tuple[str, dict[str, str]]:
        """Create redacted text and a mapping for restoration."""
        mapping: dict[str, str] = {}
        result_text = text
        counter = 0
        for name, pattern in self._patterns.items():
            for m in pattern.finditer(result_text):
                original = m.group()
                placeholder = f"[REDACTED:{name}:{counter}]"
                mapping[placeholder] = original
                result_text = result_text.replace(original, placeholder, 1)
                counter += 1
        return result_text, mapping

    def patterns(self) -> dict[str, str]:
        """Return current pattern definitions."""
        return {name: pat.pattern for name, pat in self._patterns.items()}

    def report(self, text: str) -> dict:
        """Report what would be redacted without modifying text."""
        detections: list[dict] = []
        for name, pattern in self._patterns.items():
            for m in pattern.finditer(text):
                detections.append({
                    "type": name,
                    "match": m.group(),
                    "position": m.start(),
                })
        types_found = sorted({d["type"] for d in detections})
        return {
            "total": len(detections),
            "types": types_found,
            "detections": detections,
        }
