"""Comment and test analysis agents — Task 1043."""

from __future__ import annotations

import re
from typing import Sequence

from lidco.review.pipeline import ReviewAgent, ReviewIssue, ReviewSeverity


class CommentAnalyzer(ReviewAgent):
    """Analyze comments and docstrings in diff for quality issues."""

    @property
    def name(self) -> str:
        return "comment-analyzer"

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

        # TODO without issue reference
        if re.search(r"#\s*TODO(?!.*(?:#\d+|issue|ticket|jira|gh-))", code, re.IGNORECASE):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="comment",
                file=file,
                line=line,
                message="TODO comment without issue reference",
                agent_name=self.name,
            ))

        # Stale comment markers (FIXME, HACK, XXX)
        if re.search(r"#\s*(FIXME|HACK|XXX)\b", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.IMPORTANT,
                category="comment",
                file=file,
                line=line,
                message="Stale marker comment found (FIXME/HACK/XXX)",
                agent_name=self.name,
            ))

        # Misleading docstring — empty docstring
        if re.search(r'"""[\s]*"""', code) or re.search(r"'''[\s]*'''", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="docstring",
                file=file,
                line=line,
                message="Empty docstring — add documentation or remove",
                agent_name=self.name,
            ))

        # Public function/class missing docstring detection
        # (heuristic: def/class at start followed by no docstring on same line)
        if re.match(r"\s*(def|class)\s+[a-zA-Z]\w*", code) and not code.strip().startswith("_"):
            # Mark as a potential — downstream checks will verify next line
            pass

        return issues


class PRTestAnalyzer(ReviewAgent):
    """Analyze test coverage gaps in PR diffs."""

    @property
    def name(self) -> str:
        return "test-analyzer"

    def analyze(self, diff: str, files: Sequence[str]) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        new_functions = self._extract_new_functions(diff)
        test_files = [f for f in files if "test" in f.lower()]
        source_files = [f for f in files if "test" not in f.lower() and f.endswith(".py")]

        # Check for source files without corresponding test files
        for src in source_files:
            has_test = any(
                src.replace("/", "_").replace(".py", "") in t.replace("/", "_")
                or src.split("/")[-1].replace(".py", "") in t
                for t in test_files
            )
            if not has_test:
                issues.append(ReviewIssue(
                    severity=ReviewSeverity.IMPORTANT,
                    category="testing",
                    file=src,
                    line=0,
                    message="Source file modified but no corresponding test file in PR",
                    agent_name=self.name,
                ))

        # Check for new functions without test coverage
        for func_info in new_functions:
            func_name = func_info["name"]
            if func_name.startswith("_"):
                continue
            # Check if any test file references this function
            found_in_test = False
            for raw_line in diff.splitlines():
                if raw_line.startswith("+") and not raw_line.startswith("+++"):
                    if func_name in raw_line and "test" in raw_line.lower():
                        found_in_test = True
                        break
            if not found_in_test:
                issues.append(ReviewIssue(
                    severity=ReviewSeverity.SUGGESTION,
                    category="testing",
                    file=func_info["file"],
                    line=func_info["line"],
                    message=f"New public function '{func_name}' — consider adding tests",
                    agent_name=self.name,
                ))

        # Detect test quality issues
        issues.extend(self._check_test_quality(diff))

        return issues

    def _extract_new_functions(self, diff: str) -> list[dict[str, object]]:
        funcs: list[dict[str, object]] = []
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
                match = re.match(r"\s*def\s+(\w+)\s*\(", code)
                if match:
                    funcs.append({
                        "name": match.group(1),
                        "file": current_file,
                        "line": line_no,
                    })
            elif not raw_line.startswith("-"):
                line_no += 1

        return funcs

    def _check_test_quality(self, diff: str) -> list[ReviewIssue]:
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
                if "test" in current_file.lower():
                    # Empty test body
                    if re.search(r"def\s+test_\w+.*:\s*$", code):
                        pass  # next line might have pass
                    if re.match(r"\s+pass\s*$", code):
                        issues.append(ReviewIssue(
                            severity=ReviewSeverity.IMPORTANT,
                            category="test-quality",
                            file=current_file,
                            line=line_no,
                            message="Test body contains only 'pass' — add assertions",
                            agent_name=self.name,
                        ))
            elif not raw_line.startswith("-"):
                line_no += 1

        return issues
