"""Performance anti-pattern detector."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PerfIssue:
    """A single performance anti-pattern."""

    rule: str
    file: str
    line: int
    message: str
    severity: str = "warning"  # "error" / "warning" / "info"
    suggestion: str = ""


@dataclass
class PerfReport:
    """Aggregated performance analysis result."""

    issues: list[PerfIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def total(self) -> int:
        return len(self.issues)

    def format(self) -> str:
        if not self.issues:
            return "No performance issues found."
        lines = [f"Found {self.total} performance issue(s):"]
        for issue in self.issues:
            loc = f"{issue.file}:{issue.line}" if issue.file else f"line {issue.line}"
            lines.append(f"  [{issue.severity.upper()}] {loc} — {issue.rule}: {issue.message}")
            if issue.suggestion:
                lines.append(f"    Suggestion: {issue.suggestion}")
        return "\n".join(lines)


# Built-in performance anti-patterns ------------------------------------------

_PERF_RULES: list[dict[str, Any]] = [
    {
        "name": "n_plus_one",
        "pattern": r"for\s+\w+\s+in\s+.*:\s*\n\s+.*\b(?:execute|query|fetch|find|get)\b",
        "message": "Possible N+1 query — database call inside loop",
        "severity": "error",
        "suggestion": "Batch the query outside the loop",
        "multiline": True,
    },
    {
        "name": "regex_in_loop",
        "pattern": r"for\s+\w+\s+in\s+.*:\s*\n(?:\s+.*\n)*?\s+.*re\.(?:search|match|findall|compile)\(",
        "message": "Regex compilation inside loop",
        "severity": "warning",
        "suggestion": "Compile regex before the loop with re.compile()",
        "multiline": True,
    },
    {
        "name": "unbounded_list_growth",
        "pattern": r"while\s+True\s*:\s*\n(?:\s+.*\n)*?\s+\w+\.append\(",
        "message": "Unbounded list growth in infinite loop",
        "severity": "error",
        "suggestion": "Add a size limit or use collections.deque(maxlen=N)",
        "multiline": True,
    },
    {
        "name": "string_concat_in_loop",
        "pattern": r"for\s+\w+\s+in\s+.*:\s*\n(?:\s+.*\n)*?\s+\w+\s*\+=\s*[\"']",
        "message": "String concatenation in loop",
        "severity": "warning",
        "suggestion": "Collect in list and join: ''.join(parts)",
        "multiline": True,
    },
    {
        "name": "global_import_in_function",
        "pattern": r"def\s+\w+\s*\([^)]*\)\s*(?:->.*)?:\s*\n(?:\s+.*\n)*?\s+import\s+",
        "message": "Import inside function — moves cost to runtime",
        "severity": "info",
        "suggestion": "Move import to module level unless needed for circular dependency",
        "multiline": True,
    },
    {
        "name": "list_comprehension_to_len",
        "pattern": r"len\s*\(\s*\[.*for\s+\w+\s+in\s+",
        "message": "len() of list comprehension — use sum() with generator",
        "severity": "warning",
        "suggestion": "Use sum(1 for x in ... if ...) instead",
    },
    {
        "name": "nested_loop_quadratic",
        "pattern": r"for\s+\w+\s+in\s+.*:\s*\n\s+for\s+\w+\s+in\s+",
        "message": "Nested loops — potential O(n^2) complexity",
        "severity": "info",
        "suggestion": "Consider using dict/set lookup or itertools.product",
        "multiline": True,
    },
    {
        "name": "sleep_in_loop",
        "pattern": r"(?:while|for)\s+.*:\s*\n(?:\s+.*\n)*?\s+(?:time\.sleep|asyncio\.sleep)\s*\(",
        "message": "sleep() in loop — consider event-driven approach",
        "severity": "warning",
        "suggestion": "Use asyncio events or polling with backoff",
        "multiline": True,
    },
    {
        "name": "missing_pagination",
        "pattern": r"\.(?:all|find|select|fetch_all|list)\s*\(\s*\)",
        "message": "Fetching all records without pagination",
        "severity": "warning",
        "suggestion": "Add limit/offset or cursor-based pagination",
    },
    {
        "name": "synchronous_io_in_async",
        "pattern": r"async\s+def\s+\w+.*:\s*\n(?:\s+.*\n)*?\s+(?:open|requests\.get|requests\.post|urllib\.request)\s*\(",
        "message": "Synchronous I/O in async function",
        "severity": "error",
        "suggestion": "Use aiofiles, aiohttp, or run_in_executor",
        "multiline": True,
    },
]


class PerfAntiPatternDetector:
    """Detect performance anti-patterns in source code."""

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self._rules = rules if rules is not None else list(_PERF_RULES)

    @property
    def rules(self) -> list[dict[str, Any]]:
        return list(self._rules)

    def add_rule(self, rule: dict[str, Any]) -> None:
        self._rules = [*self._rules, rule]

    def detect(self, source: str, filename: str = "") -> PerfReport:
        """Detect performance anti-patterns in *source*."""
        issues: list[PerfIssue] = []

        for rule in self._rules:
            pattern_str = rule.get("pattern", "")
            if not pattern_str:
                continue
            flags = re.MULTILINE
            if rule.get("multiline"):
                flags |= re.DOTALL
            try:
                pat = re.compile(pattern_str, flags)
            except re.error:
                continue

            for match in pat.finditer(source):
                line_no = source[:match.start()].count("\n") + 1
                issues.append(
                    PerfIssue(
                        rule=rule.get("name", "unknown"),
                        file=filename,
                        line=line_no,
                        message=rule.get("message", ""),
                        severity=rule.get("severity", "warning"),
                        suggestion=rule.get("suggestion", ""),
                    )
                )

        return PerfReport(issues=issues)

    def detect_diff(self, diff_text: str) -> PerfReport:
        """Detect anti-patterns in added lines of a unified diff.

        For multiline rules, this falls back to scanning the full
        added blocks as a single string.
        """
        added_blocks: dict[str, list[tuple[int, str]]] = {}
        current_file = ""
        line_no = 0

        for raw_line in diff_text.splitlines():
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                if current_file not in added_blocks:
                    added_blocks[current_file] = []
                continue
            if raw_line.startswith("@@ "):
                m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw_line)
                if m:
                    line_no = int(m.group(1)) - 1
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                line_no += 1
                if current_file in added_blocks:
                    added_blocks[current_file].append((line_no, raw_line[1:]))
            elif not raw_line.startswith("-"):
                line_no += 1

        issues: list[PerfIssue] = []
        for file_path, lines in added_blocks.items():
            if not lines:
                continue
            block = "\n".join(code for _, code in lines)
            first_line = lines[0][0]

            for rule in self._rules:
                pattern_str = rule.get("pattern", "")
                if not pattern_str:
                    continue
                flags = re.MULTILINE
                if rule.get("multiline"):
                    flags |= re.DOTALL
                try:
                    pat = re.compile(pattern_str, flags)
                except re.error:
                    continue
                for match in pat.finditer(block):
                    offset = block[:match.start()].count("\n")
                    issues.append(
                        PerfIssue(
                            rule=rule.get("name", "unknown"),
                            file=file_path,
                            line=first_line + offset,
                            message=rule.get("message", ""),
                            severity=rule.get("severity", "warning"),
                            suggestion=rule.get("suggestion", ""),
                        )
                    )

        return PerfReport(issues=issues)
