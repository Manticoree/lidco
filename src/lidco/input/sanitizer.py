"""Q140 — InputSanitizer: input validation and sanitization."""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field


@dataclass
class SanitizeResult:
    """Result of sanitization."""

    original: str
    sanitized: str
    warnings: list[str] = field(default_factory=list)
    was_modified: bool = False


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAVERSAL_RE = re.compile(r"(^|[\\/])\.\.($|[\\/])")
_SHELL_INJECTION_RE = re.compile(r"[;&|`$]")
_IDENTIFIER_RE = re.compile(r"[^a-zA-Z0-9_]")


class InputSanitizer:
    """Sanitize and validate user input."""

    def sanitize(self, text: str) -> SanitizeResult:
        """Strip control chars, normalize whitespace, warn on suspicious patterns."""
        warnings: list[str] = []
        cleaned = text

        # Strip control characters
        if _CONTROL_CHAR_RE.search(cleaned):
            warnings.append("Control characters removed")
            cleaned = _CONTROL_CHAR_RE.sub("", cleaned)

        # Normalize whitespace (collapse runs, strip leading/trailing)
        normalized = " ".join(cleaned.split())
        if normalized != cleaned:
            if not warnings:
                warnings.append("Whitespace normalized")
            cleaned = normalized

        # Warn on suspicious patterns
        if _SHELL_INJECTION_RE.search(cleaned):
            warnings.append("Suspicious shell characters detected")
        if _TRAVERSAL_RE.search(cleaned):
            warnings.append("Path traversal pattern detected")

        was_modified = cleaned != text
        return SanitizeResult(
            original=text,
            sanitized=cleaned,
            warnings=warnings,
            was_modified=was_modified,
        )

    def sanitize_path(self, path: str) -> SanitizeResult:
        """Normalize path separators, prevent traversal."""
        warnings: list[str] = []
        cleaned = path.replace("\\", "/")

        # Prevent path traversal
        if _TRAVERSAL_RE.search(cleaned):
            warnings.append("Path traversal blocked")
            # Remove all ../ sequences
            while "../" in cleaned:
                cleaned = cleaned.replace("../", "")
            while "/.." in cleaned:
                cleaned = cleaned.replace("/..", "")
            if cleaned == "..":
                cleaned = "."

        # Normalize consecutive separators
        while "//" in cleaned:
            cleaned = cleaned.replace("//", "/")

        was_modified = cleaned != path
        return SanitizeResult(
            original=path,
            sanitized=cleaned,
            warnings=warnings,
            was_modified=was_modified,
        )

    def sanitize_identifier(self, name: str) -> SanitizeResult:
        """Ensure valid Python identifier, replacing invalid chars with _."""
        warnings: list[str] = []
        cleaned = name

        if not cleaned:
            return SanitizeResult(
                original=name, sanitized="_", warnings=["Empty identifier replaced"], was_modified=True
            )

        # Replace invalid characters with _
        cleaned = _IDENTIFIER_RE.sub("_", cleaned)

        # Must not start with a digit
        if cleaned and cleaned[0].isdigit():
            cleaned = "_" + cleaned
            warnings.append("Identifier cannot start with a digit")

        if cleaned != name:
            if not warnings:
                warnings.append("Invalid characters replaced with _")

        was_modified = cleaned != name
        return SanitizeResult(
            original=name,
            sanitized=cleaned,
            warnings=warnings,
            was_modified=was_modified,
        )

    def is_safe(self, text: str) -> bool:
        """Return True if text has no control chars, traversal, or shell injection."""
        if _CONTROL_CHAR_RE.search(text):
            return False
        if _TRAVERSAL_RE.search(text):
            return False
        if _SHELL_INJECTION_RE.search(text):
            return False
        return True

    def escape_for_shell(self, text: str) -> str:
        """Quote special shell characters."""
        return shlex.quote(text)
