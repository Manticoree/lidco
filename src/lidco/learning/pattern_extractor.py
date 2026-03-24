"""Auto-extract reusable coding patterns from session history."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CodingPattern:
    name: str
    description: str
    example: str          # code snippet or command illustrating the pattern
    confidence: float     # 0.0–1.0
    tags: list[str] = field(default_factory=list)
    frequency: int = 1    # how many times seen in session


@dataclass
class ExtractionResult:
    patterns: list[CodingPattern]
    source_turns: int
    total_patterns: int

    def top(self, n: int = 5) -> list[CodingPattern]:
        return sorted(self.patterns, key=lambda p: (-p.frequency, -p.confidence))[:n]

    def format_summary(self) -> str:
        if not self.patterns:
            return "No patterns extracted."
        lines = [f"Extracted {self.total_patterns} pattern(s) from {self.source_turns} turns:"]
        for p in self.top(10):
            lines.append(f"  [{p.confidence:.0%}] {p.name}: {p.description[:60]}")
        return "\n".join(lines)


# Heuristic rules: (pattern_name, regex_on_code, description, tags)
_HEURISTICS: list[tuple[str, str, str, list[str]]] = [
    ("async-await", r"\basync\s+def\b", "Uses async/await pattern", ["async", "python"]),
    ("dataclass", r"@dataclass", "Uses dataclasses for data containers", ["dataclass", "python"]),
    ("context-manager", r"\bwith\b.*:", "Uses context managers (with statements)", ["context-manager"]),
    ("list-comprehension", r"\[.+\s+for\s+\w+\s+in\s+", "Prefers list comprehensions", ["comprehension"]),
    ("type-hints", r"def\s+\w+\s*\(.*:\s*\w+", "Uses type hints in function signatures", ["typing"]),
    ("pathlib", r"\bPath\(", "Uses pathlib.Path for file operations", ["pathlib", "files"]),
    ("f-string", r'f"[^"]*\{|f\'[^\']*\{', "Uses f-strings for string formatting", ["style"]),
    ("try-except", r"\btry\s*:", "Uses try/except for error handling", ["error-handling"]),
    ("unittest-mock", r"unittest\.mock|MagicMock|patch", "Uses unittest.mock for testing", ["testing"]),
    ("pytest", r"\bpytest\b|def test_", "Uses pytest for testing", ["testing", "pytest"]),
    ("pydantic", r"\bBaseModel\b|from pydantic", "Uses Pydantic for data validation", ["pydantic"]),
    ("logging", r"\blogging\.\w+\(", "Uses standard logging", ["logging"]),
]


def _extract_entry(name: str) -> tuple[str, str, str, list[str]] | None:
    """Return the heuristic entry for a given pattern name, or None."""
    for entry in _HEURISTICS:
        if entry[0] == name:
            return entry
    return None


class PatternExtractor:
    """Extract reusable coding patterns from a list of session turns.

    A 'turn' is a dict with at least a 'content' key (the code/text).
    """

    def __init__(self, min_confidence: float = 0.3) -> None:
        self.min_confidence = min_confidence

    def _score_pattern(self, occurrences: int, total_turns: int) -> float:
        if total_turns == 0:
            return 0.0
        ratio = occurrences / total_turns
        return min(ratio * 2.0, 1.0)  # normalise: 50% hits -> 1.0

    def extract(self, turns: list[dict[str, Any]]) -> ExtractionResult:
        """Scan session turns and return observed coding patterns.

        Args:
            turns: List of dicts, each with 'content' (str) and optional 'role'.
        """
        code_turns = [t for t in turns if t.get("content")]
        combined_code = "\n".join(str(t["content"]) for t in code_turns)

        counts: dict[str, int] = {}
        examples: dict[str, str] = {}

        for name, pattern, _desc, _tags in _HEURISTICS:
            matches = re.findall(pattern, combined_code)
            if matches:
                counts[name] = len(matches)
                examples[name] = matches[0] if isinstance(matches[0], str) else str(matches[0])

        patterns: list[CodingPattern] = []
        for hname, hregex, hdesc, htags in _HEURISTICS:
            freq = counts.get(hname, 0)
            if freq == 0:
                continue
            conf = self._score_pattern(freq, max(len(code_turns), 1))
            if conf < self.min_confidence:
                continue
            patterns.append(CodingPattern(
                name=hname,
                description=hdesc,
                example=examples.get(hname, ""),
                confidence=conf,
                tags=list(htags),
                frequency=freq,
            ))

        return ExtractionResult(
            patterns=patterns,
            source_turns=len(code_turns),
            total_patterns=len(patterns),
        )

    def extract_from_diff(self, diff_text: str) -> ExtractionResult:
        """Extract patterns from a git diff string."""
        # Use added lines (+) as code context
        added_lines = [ln[1:] for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        code = "\n".join(added_lines)
        return self.extract([{"content": code, "role": "diff"}])
