"""Legacy Decoder — decode legacy code, explain cryptic patterns, provide context.

Provides ``LegacyDecoder`` that analyses source snippets and explains
legacy patterns, historical context, and likely original requirements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CodePattern:
    """A detected legacy/cryptic pattern in source code."""

    name: str
    description: str
    line_range: tuple[int, int]  # (start, end) 1-based
    severity: str = "info"  # "info", "warning", "critical"
    suggestion: str = ""

    def label(self) -> str:
        return f"[{self.severity.upper()}] {self.name}"


@dataclass(frozen=True)
class DecoderResult:
    """Result of decoding a source snippet."""

    source_name: str
    patterns: tuple[CodePattern, ...]
    historical_context: str
    original_requirements: str
    total_lines: int

    @property
    def pattern_count(self) -> int:
        return len(self.patterns)

    def summary(self) -> str:
        lines = [
            f"Decoded '{self.source_name}' ({self.total_lines} lines)",
            f"Patterns found: {self.pattern_count}",
        ]
        for p in self.patterns:
            lines.append(f"  {p.label()} (L{p.line_range[0]}–{p.line_range[1]})")
            if p.suggestion:
                lines.append(f"    Suggestion: {p.suggestion}")
        if self.historical_context:
            lines.append(f"Context: {self.historical_context}")
        if self.original_requirements:
            lines.append(f"Requirements: {self.original_requirements}")
        return "\n".join(lines)


# ---- Known legacy patterns ----
_LEGACY_DETECTORS: list[tuple[str, str, str, str]] = [
    # (regex, name, description, suggestion)
    (
        r"(?i)#\s*(?:hack|fixme|xxx|kludge)",
        "hack-comment",
        "Developer hack/fixme marker indicating technical debt",
        "Review and address the underlying issue",
    ),
    (
        r"(?i)#\s*todo",
        "todo-comment",
        "Unfinished work marker",
        "Complete or create a ticket for tracking",
    ),
    (
        r"(?:exec|eval)\s*\(",
        "dynamic-exec",
        "Dynamic code execution — security and maintainability risk",
        "Replace with explicit dispatch or configuration",
    ),
    (
        r"(?i)global\s+\w+",
        "global-variable",
        "Global mutable state — makes testing and reasoning difficult",
        "Refactor to pass state explicitly or use dependency injection",
    ),
    (
        r"except\s*:",
        "bare-except",
        "Bare except catches all exceptions including SystemExit",
        "Catch specific exceptions instead",
    ),
    (
        r"import\s+\*",
        "star-import",
        "Wildcard import — namespace pollution and unclear dependencies",
        "Use explicit imports",
    ),
    (
        r"(?:magic.number|[^a-zA-Z_]\d{3,}[^a-zA-Z_])",
        "magic-number",
        "Unexplained numeric literal (possible magic number)",
        "Extract into a named constant",
    ),
    (
        r"(?i)deprecated",
        "deprecated-marker",
        "Code marked as deprecated",
        "Plan migration to the replacement API",
    ),
]


class LegacyDecoder:
    """Decode legacy code and explain cryptic patterns.

    Parameters
    ----------
    extra_patterns:
        Additional ``(regex, name, description, suggestion)`` tuples
        to extend the built-in detectors.
    """

    def __init__(
        self,
        extra_patterns: list[tuple[str, str, str, str]] | None = None,
    ) -> None:
        self._patterns = list(_LEGACY_DETECTORS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)

    @property
    def detector_count(self) -> int:
        return len(self._patterns)

    def decode(self, source: str, name: str = "<snippet>") -> DecoderResult:
        """Analyse *source* and return a ``DecoderResult``."""
        lines = source.splitlines()
        detected: list[CodePattern] = []
        for regex, pname, desc, suggestion in self._patterns:
            compiled = re.compile(regex)
            for i, line in enumerate(lines, 1):
                if compiled.search(line):
                    detected.append(
                        CodePattern(
                            name=pname,
                            description=desc,
                            line_range=(i, i),
                            severity=self._severity_for(pname),
                            suggestion=suggestion,
                        )
                    )
        historical = self._infer_context(lines)
        requirements = self._infer_requirements(lines)
        return DecoderResult(
            source_name=name,
            patterns=tuple(detected),
            historical_context=historical,
            original_requirements=requirements,
            total_lines=len(lines),
        )

    def explain_pattern(self, pattern_name: str) -> str:
        """Return a human explanation for a known pattern name."""
        for _, pname, desc, suggestion in self._patterns:
            if pname == pattern_name:
                return f"{pname}: {desc}. Suggestion: {suggestion}"
        return f"Unknown pattern: {pattern_name}"

    # -- private helpers --

    @staticmethod
    def _severity_for(pattern_name: str) -> str:
        critical = {"dynamic-exec", "bare-except"}
        warning = {"global-variable", "star-import", "magic-number"}
        if pattern_name in critical:
            return "critical"
        if pattern_name in warning:
            return "warning"
        return "info"

    @staticmethod
    def _infer_context(lines: list[str]) -> str:
        """Try to extract historical context from docstrings / comments."""
        comments = [l.strip() for l in lines if l.strip().startswith("#")]
        if not comments:
            return "No inline documentation found."
        return f"Found {len(comments)} comment(s) — review for historical notes."

    @staticmethod
    def _infer_requirements(lines: list[str]) -> str:
        """Heuristic: look for docstrings at top of file."""
        in_docstring = False
        doc_lines: list[str] = []
        for line in lines[:30]:  # only scan top 30 lines
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_docstring:
                    break
                in_docstring = True
                content = stripped[3:]
                if content.endswith('"""') or content.endswith("'''"):
                    doc_lines.append(content[:-3])
                    break
                doc_lines.append(content)
                continue
            if in_docstring:
                doc_lines.append(stripped)
        if doc_lines:
            return " ".join(doc_lines).strip()[:200]
        return "No module-level docstring found."
