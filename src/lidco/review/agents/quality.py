"""Code quality and simplification agents — Task 1045."""

from __future__ import annotations

import re
from typing import Sequence

from lidco.review.pipeline import ReviewAgent, ReviewIssue, ReviewSeverity


class CodeQualityReviewer(ReviewAgent):
    """Review code quality: complexity, naming, duplication, magic numbers."""

    @property
    def name(self) -> str:
        return "quality-reviewer"

    def analyze(self, diff: str, files: Sequence[str]) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        current_file = ""
        line_no = 0
        indent_stack: list[int] = []

        for raw_line in diff.splitlines():
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                indent_stack = []
                continue
            if raw_line.startswith("@@ "):
                m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw_line)
                if m:
                    line_no = int(m.group(1)) - 1
                indent_stack = []
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                line_no += 1
                code = raw_line[1:]
                issues.extend(self._check_line(code, current_file, line_no, indent_stack))
            elif not raw_line.startswith("-"):
                line_no += 1

        return issues

    def _check_line(
        self, code: str, file: str, line: int, indent_stack: list[int]
    ) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        stripped = code.rstrip()
        if not stripped:
            return issues

        # Deep nesting detection (>4 levels)
        leading = len(code) - len(code.lstrip())
        indent_level = leading // 4 if leading > 0 else 0
        if indent_level > 4:
            issues.append(ReviewIssue(
                severity=ReviewSeverity.IMPORTANT,
                category="complexity",
                file=file,
                line=line,
                message=f"Deep nesting ({indent_level} levels) — consider extracting to a function",
                agent_name=self.name,
            ))

        # Magic numbers (numeric literals that are not 0, 1, -1, 2)
        if re.search(r"(?<![a-zA-Z_\"])(?<!\d\.)\b(\d{3,})\b(?!\.?\d)", code):
            # Only flag if not in a comment and not a common constant
            if not code.lstrip().startswith("#"):
                issues.append(ReviewIssue(
                    severity=ReviewSeverity.SUGGESTION,
                    category="readability",
                    file=file,
                    line=line,
                    message="Magic number — consider extracting to a named constant",
                    agent_name=self.name,
                ))

        # Long line
        if len(stripped) > 120:
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="readability",
                file=file,
                line=line,
                message=f"Line too long ({len(stripped)} chars) — max 120 recommended",
                agent_name=self.name,
            ))

        # Single-letter variable names (except i, j, k, x, y, _, e)
        if re.match(r"\s*([a-hln-wz])\s*=\s*", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="naming",
                file=file,
                line=line,
                message="Single-letter variable name — use a descriptive name",
                agent_name=self.name,
            ))

        # Boolean comparison (== True / == False)
        if re.search(r"==\s*(True|False)\b", code) or re.search(r"(True|False)\s*==", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="readability",
                file=file,
                line=line,
                message="Explicit boolean comparison — simplify to 'if x:' or 'if not x:'",
                agent_name=self.name,
            ))

        return issues


class CodeSimplifier(ReviewAgent):
    """Suggest code simplifications: dead code, unnecessary abstractions."""

    @property
    def name(self) -> str:
        return "simplifier"

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

        # Unnecessary pass (in non-empty block — heuristic: pass after code)
        # This is simplistic but useful for standalone pass-only functions
        if re.match(r"\s+pass\s*$", code):
            # Already reported by other agents, flag as simplification
            pass

        # if x: return True else: return False
        if re.search(r"return\s+True\s*$", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="simplification",
                file=file,
                line=line,
                message="'return True/False' pattern — consider 'return <condition>' directly",
                agent_name=self.name,
            ))

        # Unnecessary else after return
        if re.match(r"\s*else\s*:", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="simplification",
                file=file,
                line=line,
                message="'else' after return/raise — consider removing else block (early return)",
                agent_name=self.name,
            ))

        # Chained isinstance
        if re.search(r"isinstance\s*\(\s*\w+\s*,\s*\w+\s*\)\s*(and|or)\s*isinstance", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="simplification",
                file=file,
                line=line,
                message="Chained isinstance — use isinstance(x, (A, B)) tuple form",
                agent_name=self.name,
            ))

        # len(x) == 0 / len(x) > 0
        if re.search(r"len\(\w+\)\s*[=!><]=?\s*0", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="simplification",
                file=file,
                line=line,
                message="'len(x) == 0' — use 'not x' or 'if x:' for truthiness check",
                agent_name=self.name,
            ))

        # Dead import (import but line starts with #)
        # Cannot fully detect dead imports in diff, but flag commented imports
        if re.match(r"\s*#\s*(import|from)\s+", code):
            issues.append(ReviewIssue(
                severity=ReviewSeverity.SUGGESTION,
                category="dead-code",
                file=file,
                line=line,
                message="Commented-out import — remove if not needed",
                agent_name=self.name,
            ))

        return issues
