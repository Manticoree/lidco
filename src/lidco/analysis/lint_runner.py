"""Lint result aggregation — Task 342."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class LintIssue:
    file: str
    line: int
    col: int
    code: str
    message: str
    severity: Severity = Severity.WARNING


@dataclass
class LintReport:
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    @property
    def total(self) -> int:
        return len(self.issues)

    def by_file(self) -> dict[str, list[LintIssue]]:
        result: dict[str, list[LintIssue]] = {}
        for issue in self.issues:
            result.setdefault(issue.file, []).append(issue)
        return result

    def filter_severity(self, severity: Severity) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == severity]


# Ruff output: path:line:col: CODE message
_RUFF_RE = re.compile(r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$")
# Flake8/pycodestyle output: path:line:col: CODE message
_FLAKE8_RE = _RUFF_RE
# Mypy output: path:line: error/note/warning: message  [code]
_MYPY_RE = re.compile(r"^(.+?):(\d+):\s+(error|warning|note):\s+(.+?)(?:\s+\[(.+?)\])?$")


_ERROR_CODES = frozenset({
    "E", "F",  # Ruff/flake8 errors
})


def _is_error_code(code: str) -> bool:
    return code.startswith(("E", "F")) and not code.startswith("W")


class LintRunner:
    """Parse lint tool output into a unified LintReport."""

    def parse_ruff(self, output: str) -> LintReport:
        """Parse ``ruff check`` output."""
        return self._parse_generic(output)

    def parse_flake8(self, output: str) -> LintReport:
        """Parse ``flake8`` output."""
        return self._parse_generic(output)

    def parse_mypy(self, output: str) -> LintReport:
        """Parse ``mypy`` output."""
        issues: list[LintIssue] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            m = _MYPY_RE.match(line)
            if not m:
                continue
            file_path, lineno, level, message, code = m.groups()
            if level == "error":
                severity = Severity.ERROR
            elif level == "warning":
                severity = Severity.WARNING
            else:
                severity = Severity.INFO
            issues.append(
                LintIssue(
                    file=file_path,
                    line=int(lineno),
                    col=0,
                    code=code or level,
                    message=message.strip(),
                    severity=severity,
                )
            )
        return LintReport(issues=issues)

    def merge(self, *reports: LintReport) -> LintReport:
        """Merge multiple LintReports into one."""
        merged: list[LintIssue] = []
        seen: set[tuple] = set()
        for report in reports:
            for issue in report.issues:
                key = (issue.file, issue.line, issue.col, issue.code)
                if key not in seen:
                    seen.add(key)
                    merged.append(issue)
        return LintReport(issues=merged)

    def _parse_generic(self, output: str) -> LintReport:
        issues: list[LintIssue] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            m = _RUFF_RE.match(line)
            if not m:
                continue
            file_path, lineno, col, code, message = m.groups()
            severity = Severity.ERROR if _is_error_code(code) else Severity.WARNING
            issues.append(
                LintIssue(
                    file=file_path,
                    line=int(lineno),
                    col=int(col),
                    code=code,
                    message=message.strip(),
                    severity=severity,
                )
            )
        return LintReport(issues=issues)
