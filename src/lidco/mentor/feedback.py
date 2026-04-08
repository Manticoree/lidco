"""Feedback Generator — Generate constructive code review feedback.

Identify strengths, improvement areas, provide specific examples,
and generate actionable items.  Pure stdlib, no external dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


# ---------------------------------------------------------------------------
# Enums & Data classes
# ---------------------------------------------------------------------------

class Severity(Enum):
    """Feedback item severity."""

    INFO = "info"
    SUGGESTION = "suggestion"
    WARNING = "warning"
    CRITICAL = "critical"


class Category(Enum):
    """Feedback category."""

    READABILITY = "readability"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TESTING = "testing"
    ARCHITECTURE = "architecture"
    NAMING = "naming"
    ERROR_HANDLING = "error_handling"
    DOCUMENTATION = "documentation"
    STYLE = "style"
    BEST_PRACTICE = "best_practice"


@dataclass(frozen=True)
class Strength:
    """A strength identified in the code."""

    description: str
    example: str = ""
    category: Category = Category.BEST_PRACTICE


@dataclass(frozen=True)
class ImprovementArea:
    """An area where code can be improved."""

    description: str
    severity: Severity = Severity.SUGGESTION
    category: Category = Category.BEST_PRACTICE
    example: str = ""
    suggestion: str = ""
    line: int = 0


@dataclass(frozen=True)
class ActionItem:
    """A concrete action item for improvement."""

    title: str
    description: str
    priority: int = 2  # 1 (highest) .. 5 (lowest)
    category: Category = Category.BEST_PRACTICE
    estimated_effort: str = "small"  # small, medium, large


@dataclass
class FeedbackReport:
    """A complete feedback report."""

    title: str
    summary: str = ""
    strengths: list[Strength] = field(default_factory=list)
    improvements: list[ImprovementArea] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    overall_score: float = 0.0  # 0.0 .. 10.0

    @property
    def strength_count(self) -> int:
        return len(self.strengths)

    @property
    def improvement_count(self) -> int:
        return len(self.improvements)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.improvements if i.severity == Severity.CRITICAL)

    @property
    def label(self) -> str:
        if self.overall_score >= 8.0:
            return "excellent"
        if self.overall_score >= 6.0:
            return "good"
        if self.overall_score >= 4.0:
            return "needs improvement"
        return "significant issues"


# ---------------------------------------------------------------------------
# Built-in code quality checks
# ---------------------------------------------------------------------------

_QUALITY_CHECKS: list[dict[str, str]] = [
    {
        "name": "long_function",
        "pattern": r"^(def |async def )",
        "category": "readability",
        "message": "Function may be too long. Consider breaking it into smaller functions.",
    },
    {
        "name": "bare_except",
        "pattern": r"except\s*:",
        "category": "error_handling",
        "message": "Bare except catches all exceptions including KeyboardInterrupt. Use specific exception types.",
    },
    {
        "name": "todo_comment",
        "pattern": r"#\s*TODO",
        "category": "documentation",
        "message": "TODO comment found. Consider tracking in an issue tracker.",
    },
    {
        "name": "magic_number",
        "pattern": r"(?<!=\s)\b(?!0\b|1\b|2\b)\d{2,}\b",
        "category": "readability",
        "message": "Magic number detected. Consider extracting to a named constant.",
    },
    {
        "name": "print_statement",
        "pattern": r"\bprint\s*\(",
        "category": "best_practice",
        "message": "Print statement found. Consider using logging instead.",
    },
    {
        "name": "global_statement",
        "pattern": r"\bglobal\s+\w",
        "category": "architecture",
        "message": "Global statement found. Consider passing values as parameters instead.",
    },
]


# ---------------------------------------------------------------------------
# FeedbackGenerator
# ---------------------------------------------------------------------------

class FeedbackGenerator:
    """Generate constructive feedback for code."""

    def __init__(self) -> None:
        self._checks = list(_QUALITY_CHECKS)

    # -- Analysis ------------------------------------------------------------

    def analyze_code(self, code: str, *, title: str = "Code Review") -> FeedbackReport:
        """Analyze code and generate a feedback report."""
        lines = code.split("\n")
        report = FeedbackReport(title=title)

        strengths = self._find_strengths(lines)
        improvements = self._find_improvements(lines)

        report.strengths = strengths
        report.improvements = improvements
        report.action_items = self._generate_action_items(improvements)
        report.summary = self._generate_summary(report)
        report.overall_score = self._compute_score(report, len(lines))

        return report

    def _find_strengths(self, lines: list[str]) -> list[Strength]:
        """Identify good practices in the code."""
        strengths: list[Strength] = []

        code = "\n".join(lines)

        # Check for docstrings
        if '"""' in code or "'''" in code:
            strengths.append(Strength(
                description="Code includes docstrings for documentation.",
                category=Category.DOCUMENTATION,
            ))

        # Check for type hints
        if "->" in code or ": str" in code or ": int" in code or ": list" in code:
            strengths.append(Strength(
                description="Type hints are used for better code clarity.",
                category=Category.READABILITY,
            ))

        # Check for error handling
        if "try:" in code and "except" in code:
            strengths.append(Strength(
                description="Error handling is present.",
                category=Category.ERROR_HANDLING,
            ))

        # Check for tests
        if "def test_" in code or "assert " in code:
            strengths.append(Strength(
                description="Tests or assertions are included.",
                category=Category.TESTING,
            ))

        # Check for constants (UPPER_CASE)
        for line in lines:
            stripped = line.strip()
            if re.match(r"^[A-Z_]{2,}\s*=", stripped):
                strengths.append(Strength(
                    description="Named constants are used instead of magic values.",
                    category=Category.READABILITY,
                ))
                break

        return strengths

    def _find_improvements(self, lines: list[str]) -> list[ImprovementArea]:
        """Find areas for improvement."""
        improvements: list[ImprovementArea] = []
        func_lines = 0
        in_function = False

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Run pattern-based checks
            for check in self._checks:
                if re.search(check["pattern"], stripped):
                    cat_str = check["category"]
                    try:
                        cat = Category(cat_str)
                    except ValueError:
                        cat = Category.BEST_PRACTICE

                    improvements.append(ImprovementArea(
                        description=check["message"],
                        category=cat,
                        severity=Severity.SUGGESTION,
                        line=i,
                    ))

            # Track function length
            if re.match(r"^(def |async def )", stripped):
                if in_function and func_lines > 50:
                    improvements.append(ImprovementArea(
                        description=f"Function is {func_lines} lines long (>50). Consider splitting.",
                        category=Category.READABILITY,
                        severity=Severity.WARNING,
                        line=i - func_lines,
                    ))
                in_function = True
                func_lines = 0
            elif in_function:
                func_lines += 1

            # Deep nesting check
            leading = len(line) - len(line.lstrip())
            spaces_per_indent = 4
            depth = leading // spaces_per_indent if spaces_per_indent else 0
            if depth > 4 and stripped:
                improvements.append(ImprovementArea(
                    description=f"Deep nesting (level {depth}) at line {i}. Consider early returns or extraction.",
                    category=Category.READABILITY,
                    severity=Severity.WARNING,
                    line=i,
                ))

        return improvements

    def _generate_action_items(self, improvements: list[ImprovementArea]) -> list[ActionItem]:
        """Generate action items from improvements."""
        seen: set[str] = set()
        items: list[ActionItem] = []

        for imp in improvements:
            key = f"{imp.category.value}:{imp.description[:50]}"
            if key in seen:
                continue
            seen.add(key)

            priority = 1 if imp.severity == Severity.CRITICAL else (
                2 if imp.severity == Severity.WARNING else 3
            )

            items.append(ActionItem(
                title=f"Address {imp.category.value} issue",
                description=imp.description,
                priority=priority,
                category=imp.category,
                estimated_effort="small" if imp.severity != Severity.CRITICAL else "medium",
            ))

        items.sort(key=lambda a: a.priority)
        return items

    def _generate_summary(self, report: FeedbackReport) -> str:
        """Generate a human-readable summary."""
        parts: list[str] = []
        if report.strengths:
            parts.append(f"{len(report.strengths)} strength(s) identified")
        if report.improvements:
            parts.append(f"{len(report.improvements)} improvement(s) suggested")
        if report.critical_count:
            parts.append(f"{report.critical_count} critical issue(s)")
        return ". ".join(parts) + "." if parts else "No issues found."

    def _compute_score(self, report: FeedbackReport, line_count: int) -> float:
        """Compute an overall score (0..10)."""
        if line_count == 0:
            return 10.0

        score = 10.0

        # Deductions for improvements
        for imp in report.improvements:
            if imp.severity == Severity.CRITICAL:
                score -= 2.0
            elif imp.severity == Severity.WARNING:
                score -= 0.5
            else:
                score -= 0.2

        # Bonuses for strengths
        score += len(report.strengths) * 0.3

        return max(0.0, min(10.0, score))

    # -- Custom checks -------------------------------------------------------

    def add_check(
        self,
        name: str,
        pattern: str,
        message: str,
        category: str = "best_practice",
    ) -> None:
        """Add a custom quality check."""
        self._checks.append({
            "name": name,
            "pattern": pattern,
            "category": category,
            "message": message,
        })

    def remove_check(self, name: str) -> bool:
        """Remove a check by name."""
        before = len(self._checks)
        self._checks = [c for c in self._checks if c["name"] != name]
        return len(self._checks) < before
