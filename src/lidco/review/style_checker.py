"""Style consistency checker — learn project style and flag deviations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StyleViolation:
    """A single style deviation."""

    rule: str
    file: str
    line: int
    message: str
    suggestion: str = ""
    severity: str = "warning"  # "error" / "warning" / "info"


@dataclass
class StyleReport:
    """Aggregated style check result."""

    violations: list[StyleViolation] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    def format(self) -> str:
        if not self.violations:
            return "No style violations found."
        lines = [f"Found {len(self.violations)} style violation(s):"]
        for v in self.violations:
            loc = f"{v.file}:{v.line}" if v.file else f"line {v.line}"
            lines.append(f"  [{v.severity.upper()}] {loc} — {v.rule}: {v.message}")
            if v.suggestion:
                lines.append(f"    Suggestion: {v.suggestion}")
        return "\n".join(lines)


# Built-in style rules -------------------------------------------------------

_BUILTIN_RULES: list[dict[str, Any]] = [
    {
        "name": "trailing_whitespace",
        "pattern": r"[ \t]+$",
        "message": "Trailing whitespace",
        "suggestion": "Remove trailing spaces/tabs",
        "severity": "warning",
    },
    {
        "name": "tabs_instead_of_spaces",
        "pattern": r"^\t+",
        "message": "Tab indentation detected (project uses spaces)",
        "suggestion": "Convert tabs to spaces",
        "severity": "warning",
    },
    {
        "name": "multiple_blank_lines",
        "pattern": r"\n{4,}",
        "message": "More than 2 consecutive blank lines",
        "suggestion": "Reduce to at most 2 blank lines",
        "severity": "info",
    },
    {
        "name": "wildcard_import",
        "pattern": r"^from\s+\S+\s+import\s+\*",
        "message": "Wildcard import",
        "suggestion": "Import specific names instead of *",
        "severity": "error",
    },
    {
        "name": "print_statement",
        "pattern": r"^\s*print\s*\(",
        "message": "print() statement (use logging instead)",
        "suggestion": "Replace with logging.debug/info/warning",
        "severity": "warning",
    },
    {
        "name": "magic_number",
        "pattern": r"(?<![.\w])\b(?!0\b|1\b|2\b|100\b)\d{3,}\b(?![.\w])",
        "message": "Magic number — consider named constant",
        "suggestion": "Extract to a named constant",
        "severity": "info",
    },
    {
        "name": "long_line",
        "pattern": r"^.{121,}$",
        "message": "Line exceeds 120 characters",
        "suggestion": "Break line to fit within 120 characters",
        "severity": "warning",
    },
    {
        "name": "todo_without_owner",
        "pattern": r"#\s*TODO(?!\s*\()",
        "message": "TODO without owner",
        "suggestion": "Add owner: # TODO(username): ...",
        "severity": "info",
    },
]


class StyleConsistencyChecker:
    """Check code for style consistency violations."""

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self._rules = rules if rules is not None else list(_BUILTIN_RULES)

    @property
    def rules(self) -> list[dict[str, Any]]:
        return list(self._rules)

    def add_rule(self, rule: dict[str, Any]) -> None:
        self._rules = [*self._rules, rule]

    def check(self, source: str, filename: str = "") -> StyleReport:
        """Check *source* for style violations."""
        violations: list[StyleViolation] = []

        for rule in self._rules:
            pattern_str = rule.get("pattern", "")
            if not pattern_str:
                continue
            try:
                pat = re.compile(pattern_str, re.MULTILINE)
            except re.error:
                continue

            for match in pat.finditer(source):
                line_no = source[:match.start()].count("\n") + 1
                violations.append(
                    StyleViolation(
                        rule=rule.get("name", "unknown"),
                        file=filename,
                        line=line_no,
                        message=rule.get("message", ""),
                        suggestion=rule.get("suggestion", ""),
                        severity=rule.get("severity", "warning"),
                    )
                )

        return StyleReport(violations=violations)

    def check_diff(self, diff_text: str) -> StyleReport:
        """Check only added lines from a unified diff."""
        violations: list[StyleViolation] = []
        current_file = ""
        line_no = 0

        for raw_line in diff_text.splitlines():
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                continue
            if raw_line.startswith("@@ "):
                m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw_line)
                if m:
                    line_no = int(m.group(1)) - 1
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                line_no += 1
                code = raw_line[1:]
                for rule in self._rules:
                    pattern_str = rule.get("pattern", "")
                    if not pattern_str:
                        continue
                    try:
                        if re.search(pattern_str, code):
                            violations.append(
                                StyleViolation(
                                    rule=rule.get("name", "unknown"),
                                    file=current_file,
                                    line=line_no,
                                    message=rule.get("message", ""),
                                    suggestion=rule.get("suggestion", ""),
                                    severity=rule.get("severity", "warning"),
                                )
                            )
                    except re.error:
                        continue
            elif not raw_line.startswith("-"):
                line_no += 1

        return StyleReport(violations=violations)

    def learn_style(self, sources: list[str]) -> dict[str, Any]:
        """Analyze existing code to learn style patterns.

        Returns a dict of observed style metrics.
        """
        indent_tabs = 0
        indent_spaces = 0
        max_lines: list[int] = []
        quote_single = 0
        quote_double = 0

        for source in sources:
            lines = source.splitlines()
            max_lines.append(len(lines))
            for line in lines:
                if line.startswith("\t"):
                    indent_tabs += 1
                elif re.match(r"^ {2,}", line):
                    indent_spaces += 1
                quote_single += line.count("'")
                quote_double += line.count('"')

        return {
            "indent_style": "tabs" if indent_tabs > indent_spaces else "spaces",
            "indent_tabs_count": indent_tabs,
            "indent_spaces_count": indent_spaces,
            "quote_style": "double" if quote_double > quote_single else "single",
            "avg_file_length": sum(max_lines) / max(len(max_lines), 1),
            "files_analyzed": len(sources),
        }
