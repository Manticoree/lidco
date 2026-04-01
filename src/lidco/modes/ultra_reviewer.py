"""Deep code review from 6 perspectives."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Perspective(str, Enum):
    """Review perspective categories."""

    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    LOGIC = "logic"
    TESTS = "tests"
    SIMPLIFICATION = "simplification"


@dataclass(frozen=True)
class ReviewFinding:
    """A single finding from a review perspective."""

    perspective: Perspective
    severity: str = "medium"
    file: str = ""
    line: int = 0
    message: str = ""
    suggestion: str = ""


@dataclass(frozen=True)
class UltraReview:
    """Aggregated review result."""

    findings: tuple[ReviewFinding, ...] = ()
    perspectives_used: tuple[Perspective, ...] = ()
    source_lines: int = 0


class UltraReviewer:
    """Deep code reviewer running 6 perspective checks."""

    def __init__(self) -> None:
        self._rules: dict[Perspective, list[str]] = {p: [] for p in Perspective}

    def review(self, source: str, file: str = "") -> UltraReview:
        """Run all perspectives on source code."""
        findings: list[ReviewFinding] = []
        findings.extend(self.review_security(source, file))
        findings.extend(self.review_performance(source, file))
        findings.extend(self.review_style(source, file))
        findings.extend(self.review_logic(source, file))
        findings.extend(self.review_tests(source, file))
        findings.extend(self.review_simplification(source, file))
        line_count = len(source.splitlines()) if source else 0
        return UltraReview(
            findings=tuple(findings),
            perspectives_used=tuple(Perspective),
            source_lines=line_count,
        )

    def review_security(self, source: str, file: str = "") -> list[ReviewFinding]:
        """Check for security issues."""
        findings: list[ReviewFinding] = []
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if re.search(r'\beval\s*\(', stripped):
                findings.append(ReviewFinding(
                    Perspective.SECURITY, "high", file, i,
                    "Use of eval() detected.", "Avoid eval(); use ast.literal_eval or safer alternatives.",
                ))
            if re.search(r'\bexec\s*\(', stripped):
                findings.append(ReviewFinding(
                    Perspective.SECURITY, "high", file, i,
                    "Use of exec() detected.", "Avoid exec(); find a safer approach.",
                ))
            if re.search(r'(api_key|password|secret)\s*=\s*["\']', stripped, re.IGNORECASE):
                findings.append(ReviewFinding(
                    Perspective.SECURITY, "critical", file, i,
                    "Possible hardcoded secret.", "Use environment variables instead.",
                ))
            if re.search(r'f["\'].*SELECT.*\{', stripped) or re.search(r'%s.*SELECT|SELECT.*%', stripped):
                findings.append(ReviewFinding(
                    Perspective.SECURITY, "high", file, i,
                    "Possible SQL injection via string formatting.",
                    "Use parameterized queries.",
                ))
        return findings

    def review_performance(self, source: str, file: str = "") -> list[ReviewFinding]:
        """Check for performance issues."""
        findings: list[ReviewFinding] = []
        lines = source.splitlines()
        indent_stack: list[int] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r'for\s+', stripped) or re.match(r'while\s+', stripped):
                indent = len(line) - len(line.lstrip())
                while indent_stack and indent_stack[-1] >= indent:
                    indent_stack.pop()
                indent_stack.append(indent)
                if len(indent_stack) >= 3:
                    findings.append(ReviewFinding(
                        Perspective.PERFORMANCE, "medium", file, i,
                        "Deeply nested loop detected (3+ levels).",
                        "Consider refactoring to reduce nesting.",
                    ))
            elif stripped and not stripped.startswith("#"):
                indent = len(line) - len(line.lstrip())
                while indent_stack and indent_stack[-1] >= indent:
                    indent_stack.pop()
        return findings

    def review_style(self, source: str, file: str = "") -> list[ReviewFinding]:
        """Check for style issues."""
        findings: list[ReviewFinding] = []
        for i, line in enumerate(source.splitlines(), 1):
            if len(line) > 120:
                findings.append(ReviewFinding(
                    Perspective.STYLE, "low", file, i,
                    f"Line exceeds 120 characters ({len(line)}).",
                    "Break the line for readability.",
                ))
        if "def " in source and "-> " not in source and ": " in source:
            findings.append(ReviewFinding(
                Perspective.STYLE, "low", file, 0,
                "Functions may be missing return type hints.",
                "Add return type annotations.",
            ))
        return findings

    def review_logic(self, source: str, file: str = "") -> list[ReviewFinding]:
        """Check for logic issues."""
        findings: list[ReviewFinding] = []
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if stripped == "except:":
                findings.append(ReviewFinding(
                    Perspective.LOGIC, "medium", file, i,
                    "Bare except clause catches all exceptions.",
                    "Specify the exception type (e.g., except ValueError:).",
                ))
            if re.match(r'if\s+True\s*:', stripped):
                findings.append(ReviewFinding(
                    Perspective.LOGIC, "medium", file, i,
                    "Always-true condition detected.",
                    "Remove the condition or replace with actual logic.",
                ))
        return findings

    def review_tests(self, source: str, file: str = "") -> list[ReviewFinding]:
        """Check for test quality issues."""
        findings: list[ReviewFinding] = []
        if "def test_" in source and "assert" not in source:
            findings.append(ReviewFinding(
                Perspective.TESTS, "high", file, 0,
                "Test functions found but no assertions.",
                "Add assert statements to validate behavior.",
            ))
        if "def test_" in source and "error" not in source.lower() and "exception" not in source.lower():
            findings.append(ReviewFinding(
                Perspective.TESTS, "medium", file, 0,
                "No error/exception test cases found.",
                "Add tests for error conditions.",
            ))
        return findings

    def review_simplification(self, source: str, file: str = "") -> list[ReviewFinding]:
        """Check for simplification opportunities."""
        findings: list[ReviewFinding] = []
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("pass") and stripped == "pass":
                if i > 1:
                    prev = source.splitlines()[i - 2].strip()
                    if prev.startswith("def ") or prev.startswith("class "):
                        findings.append(ReviewFinding(
                            Perspective.SIMPLIFICATION, "low", file, i,
                            "Empty function/class body.",
                            "Implement or add a docstring explaining why it is empty.",
                        ))
        return findings

    def summary(self, review: UltraReview) -> str:
        """One-line summary of the review."""
        by_sev: dict[str, int] = {}
        for f in review.findings:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        parts = [f"{v} {k}" for k, v in sorted(by_sev.items())]
        sev_str = ", ".join(parts) if parts else "no issues"
        return (
            f"Review: {len(review.findings)} finding(s) ({sev_str}) "
            f"across {len(review.perspectives_used)} perspectives, "
            f"{review.source_lines} lines reviewed."
        )
