"""Silent failure and type design analysis agents — Task 1044."""

from __future__ import annotations

import re
from typing import Sequence

from lidco.review.pipeline import ReviewAgent, ReviewIssue, ReviewSeverity


class SilentFailureHunter(ReviewAgent):
    """Detect silent failures and swallowed errors in diff."""

    @property
    def name(self) -> str:
        return "failure-hunter"

    def analyze(self, diff: str, files: Sequence[str]) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        current_file = ""
        line_no = 0
        prev_line = ""

        for raw_line in diff.splitlines():
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
                issues.extend(
                    self._check_line(code, prev_line, current_file, line_no)
                )
                prev_line = code
            elif not raw_line.startswith("-"):
                line_no += 1
                prev_line = raw_line

        return issues

    def _check_line(
        self, code: str, prev_line: str, file: str, line: int
    ) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []

        # Bare except
        if re.match(r"\s*except\s*:", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.CRITICAL,
                category="error-handling",
                file=file,
                line=line,
                message="Bare except clause — catches all exceptions including SystemExit",
                agent_name=self.name,
            ))

        # except with pass (swallowed error)
        if re.match(r"\s*pass\s*$", code) and re.match(r"\s*except\b", prev_line):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.CRITICAL,
                category="error-handling",
                file=file,
                line=line,
                message="Exception swallowed with pass — add logging or re-raise",
                agent_name=self.name,
            ))

        # Missing error logging in except block (except with only return)
        if re.match(r"\s*return\b", code) and re.match(r"\s*except\b", prev_line):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.IMPORTANT,
                category="error-handling",
                file=file,
                line=line,
                message="Exception handler returns without logging — consider adding error log",
                agent_name=self.name,
            ))

        # Unchecked subprocess call
        if re.search(r"subprocess\.(run|call|Popen)\s*\(", code) and "check=" not in code:
            issues.append(ReviewIssue(
                severity=ReviewSeverity.IMPORTANT,
                category="error-handling",
                file=file,
                line=line,
                message="subprocess call without check=True — errors may go unnoticed",
                agent_name=self.name,
            ))

        # os.system (always unchecked)
        if re.search(r"os\.system\s*\(", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.IMPORTANT,
                category="error-handling",
                file=file,
                line=line,
                message="os.system() return value likely unchecked — use subprocess with check=True",
                agent_name=self.name,
            ))

        return issues


class TypeDesignAnalyzer(ReviewAgent):
    """Analyze type annotations and design quality in diff."""

    @property
    def name(self) -> str:
        return "type-analyzer"

    def analyze(self, diff: str, files: Sequence[str]) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        current_file = ""
        line_no = 0

        for raw_line in diff.splitlines():
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
                issues.extend(self._check_line(code, current_file, line_no))
            elif not raw_line.startswith("-"):
                line_no += 1

        return issues

    def _check_line(self, code: str, file: str, line: int) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []

        # Any usage in type annotations
        if re.search(r":\s*Any\b", code) or re.search(r"->\s*Any\b", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="typing",
                file=file,
                line=line,
                message="'Any' type annotation — consider using a more specific type",
                agent_name=self.name,
            ))

        # Missing return type annotation on public function
        if re.match(r"\s*def\s+[a-zA-Z]\w*\s*\([^)]*\)\s*:", code):
            if "->" not in code:
                issues.append(ReviewIssue(
                    severity=ReviewSeverity.SUGGESTION,
                    category="typing",
                    file=file,
                    line=line,
                    message="Public function missing return type annotation",
                    agent_name=self.name,
                ))

        # Overly broad Union with many types
        if re.search(r"Union\[(?:[^,\]]+,\s*){3,}", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="typing",
                file=file,
                line=line,
                message="Union with 4+ types — consider a Protocol or base class",
                agent_name=self.name,
            ))

        # dict without type params
        if re.search(r":\s*dict\s*[=,)\n]", code) and "dict[" not in code:
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="typing",
                file=file,
                line=line,
                message="Bare 'dict' annotation — specify key/value types",
                agent_name=self.name,
            ))

        return issues
