"""Impact Heatmap — score files by change magnitude and complexity (Q177)."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImpactEntry:
    """Impact score for a single file."""

    file: str
    score: float
    risk_level: str  # "high", "medium", "low"


@dataclass
class HeatmapResult:
    """Result of impact analysis across files."""

    entries: list[ImpactEntry] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        return sum(e.score for e in self.entries)

    @property
    def high_risk_count(self) -> int:
        return sum(1 for e in self.entries if e.risk_level == "high")


def _count_changes(old_text: str, new_text: str) -> int:
    """Count the number of changed lines between two texts."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, n=0))
    count = 0
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            count += 1
        elif line.startswith("-") and not line.startswith("---"):
            count += 1
    return count


def _estimate_complexity(text: str) -> float:
    """Estimate code complexity based on heuristics.

    Returns a multiplier >= 1.0.
    """
    if not text.strip():
        return 1.0

    lines = text.splitlines()
    total = len(lines) or 1

    # Control flow keywords increase complexity
    control_keywords = re.compile(
        r"\b(if|else|elif|for|while|try|except|catch|switch|case|finally)\b"
    )
    control_count = sum(1 for line in lines if control_keywords.search(line))

    # Nesting depth (rough: count leading whitespace)
    max_indent = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            max_indent = max(max_indent, indent)

    # Function/class definitions
    def_count = sum(1 for line in lines if re.match(r"\s*(def |class |function |async )", line))

    complexity = 1.0
    complexity += (control_count / total) * 2.0
    complexity += min(max_indent / 20.0, 1.0)
    complexity += min(def_count / total * 3.0, 1.0)

    return max(complexity, 1.0)


def _risk_level(score: float) -> str:
    """Classify risk from score."""
    if score >= 50.0:
        return "high"
    elif score >= 20.0:
        return "medium"
    return "low"


class ImpactHeatmap:
    """Analyze a set of file changes and score them by impact."""

    def __init__(
        self,
        high_threshold: float = 50.0,
        medium_threshold: float = 20.0,
    ) -> None:
        self._high = high_threshold
        self._medium = medium_threshold

    def analyze(self, changes: dict[str, tuple[str, str]]) -> HeatmapResult:
        """Analyze changes and return scored results.

        Args:
            changes: Mapping of filename -> (old_text, new_text).

        Returns:
            HeatmapResult sorted by score descending.
        """
        entries: list[ImpactEntry] = []

        for filename, (old_text, new_text) in changes.items():
            change_count = _count_changes(old_text, new_text)
            if change_count == 0 and old_text == new_text:
                entries.append(ImpactEntry(file=filename, score=0.0, risk_level="low"))
                continue

            # Use the new text for complexity (or old if new is empty)
            target = new_text if new_text.strip() else old_text
            complexity = _estimate_complexity(target)
            score = round(change_count * complexity, 2)

            if score >= self._high:
                risk = "high"
            elif score >= self._medium:
                risk = "medium"
            else:
                risk = "low"

            entries.append(ImpactEntry(file=filename, score=score, risk_level=risk))

        # Sort by score descending
        entries.sort(key=lambda e: e.score, reverse=True)
        return HeatmapResult(entries=entries)
