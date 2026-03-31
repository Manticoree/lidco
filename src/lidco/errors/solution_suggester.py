"""Q152: Suggest solutions for common errors."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Solution:
    title: str
    steps: list[str]
    confidence: float
    category: str


class SolutionSuggester:
    """Match errors to actionable solutions via regex patterns."""

    def __init__(self) -> None:
        self._solutions: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_solution(
        self,
        error_pattern: str,
        title: str,
        steps: list[str],
        category: str = "general",
    ) -> None:
        """Register a solution keyed to *error_pattern* (regex)."""
        self._solutions.append({
            "pattern": error_pattern,
            "title": title,
            "steps": list(steps),
            "category": category,
        })

    def suggest(
        self,
        error: Exception,
        context: dict | None = None,
    ) -> list[Solution]:
        """Return all matching solutions for *error*, scored by confidence."""
        msg = f"{type(error).__name__}: {error}"
        results: list[Solution] = []
        for entry in self._solutions:
            m = re.search(entry["pattern"], msg, re.IGNORECASE)
            if m:
                # Confidence: ratio of matched span to message length
                span_len = m.end() - m.start()
                confidence = min(1.0, round(span_len / max(len(msg), 1), 2))
                # Boost confidence slightly if context provides extra signal
                if context and entry["category"] in context.get("categories", []):
                    confidence = min(1.0, confidence + 0.1)
                results.append(
                    Solution(
                        title=entry["title"],
                        steps=list(entry["steps"]),
                        confidence=confidence,
                        category=entry["category"],
                    )
                )
        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

    def best(self, error: Exception) -> Optional[Solution]:
        """Return the single highest-confidence match, or None."""
        matches = self.suggest(error)
        return matches[0] if matches else None

    def format_solutions(self, solutions: list[Solution]) -> str:
        """Format a list of solutions as a numbered, human-readable string."""
        if not solutions:
            return "No solutions found."
        lines: list[str] = []
        for i, sol in enumerate(solutions, 1):
            lines.append(f"{i}. {sol.title} (confidence: {sol.confidence:.0%}, category: {sol.category})")
            for j, step in enumerate(sol.steps, 1):
                lines.append(f"   {j}. {step}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def with_defaults(cls) -> "SolutionSuggester":
        """Return a SolutionSuggester pre-loaded with common Python solutions."""
        ss = cls()
        ss.add_solution(
            r"ModuleNotFoundError|No module named",
            "Install missing package",
            [
                "Identify the missing module name from the error.",
                "Run: pip install <module>",
                "If using a virtual env, ensure it is activated.",
            ],
            "import",
        )
        ss.add_solution(
            r"FileNotFoundError|No such file",
            "Fix file path",
            [
                "Verify the file path is correct.",
                "Check the current working directory.",
                "Use os.path.exists() to confirm before access.",
            ],
            "filesystem",
        )
        ss.add_solution(
            r"PermissionError|Permission denied",
            "Fix permissions",
            [
                "Check file/directory permissions with ls -la.",
                "Change permissions with chmod if appropriate.",
                "Run with elevated privileges if needed.",
            ],
            "filesystem",
        )
        ss.add_solution(
            r"SyntaxError|invalid syntax",
            "Fix syntax error",
            [
                "Check the line number mentioned in the traceback.",
                "Look for missing colons, brackets, or quotes.",
                "Run a linter (e.g., flake8) for detailed feedback.",
            ],
            "syntax",
        )
        ss.add_solution(
            r"ConnectionError|ConnectionRefusedError",
            "Resolve connection issue",
            [
                "Verify the target host/port is correct.",
                "Check your network/firewall settings.",
                "Ensure the remote service is running.",
            ],
            "network",
        )
        ss.add_solution(
            r"TimeoutError|timed out",
            "Handle timeout",
            [
                "Increase the timeout value.",
                "Check network latency.",
                "Add retry logic with exponential backoff.",
            ],
            "network",
        )
        ss.add_solution(
            r"ValueError|invalid literal",
            "Fix invalid value",
            [
                "Check the input data format.",
                "Add input validation before the operation.",
                "Handle edge cases (empty strings, None values).",
            ],
            "validation",
        )
        ss.add_solution(
            r"KeyError",
            "Fix missing key",
            [
                "Use dict.get(key, default) instead of dict[key].",
                "Check that the key exists before accessing it.",
                "Print available keys to debug.",
            ],
            "data",
        )
        ss.add_solution(
            r"TypeError",
            "Fix type mismatch",
            [
                "Check the types of all arguments.",
                "Use isinstance() to validate before operations.",
                "Review the function signature.",
            ],
            "typing",
        )
        ss.add_solution(
            r"ImportError",
            "Resolve import issue",
            [
                "Check for circular imports.",
                "Verify the module path is correct.",
                "Ensure __init__.py exists in the package.",
            ],
            "import",
        )
        return ss
