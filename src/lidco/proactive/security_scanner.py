"""Security pattern scanner — Task 414."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecurityIssue:
    """A single security finding."""

    file: str
    line: int
    rule_id: str
    severity: str  # "critical" | "high" | "medium" | "low"
    message: str
    snippet: str


# ---------------------------------------------------------------------------
# Regex-based patterns applied to raw source lines
# ---------------------------------------------------------------------------

_HARDCODED_SECRET_RE = re.compile(
    r"""(?xi)
    (?:password|passwd|secret|api_key|apikey|token|auth_token|access_key|private_key)
    \s*=\s*
    (?P<q>["'])(?P<val>[^"']{4,})(?P=q)
    """,
)

_SQL_CONCAT_RE = re.compile(
    r"""(?xi)
    f["']
    .*?(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\s
    """,
)

_OS_SYSTEM_RE = re.compile(r"\bos\.system\s*\(")


class SecurityScanner:
    """Scan Python source files for common security issues."""

    def scan_source(self, source: str, file_path: str = "") -> list[SecurityIssue]:
        """Scan *source* string and return findings."""
        issues: list[SecurityIssue] = []

        # Line-based regex scans
        for lineno, line in enumerate(source.splitlines(), start=1):
            snippet = line.strip()[:120]

            # Hardcoded secrets
            if _HARDCODED_SECRET_RE.search(line):
                issues.append(SecurityIssue(
                    file=file_path,
                    line=lineno,
                    rule_id="S001",
                    severity="critical",
                    message="Possible hardcoded secret/credential detected",
                    snippet=snippet,
                ))

            # SQL string concatenation via f-strings
            if _SQL_CONCAT_RE.search(line):
                issues.append(SecurityIssue(
                    file=file_path,
                    line=lineno,
                    rule_id="S002",
                    severity="high",
                    message="SQL query built with f-string — potential SQL injection",
                    snippet=snippet,
                ))

            # os.system()
            if _OS_SYSTEM_RE.search(line):
                issues.append(SecurityIssue(
                    file=file_path,
                    line=lineno,
                    rule_id="S005",
                    severity="medium",
                    message="`os.system()` used — prefer `subprocess.run()` with a list",
                    snippet=snippet,
                ))

        # AST-based scans
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            self._check_subprocess_shell(node, file_path, issues)
            self._check_eval(node, file_path, issues)

        return issues

    def scan_file(self, file_path: str) -> list[SecurityIssue]:
        """Read *file_path* and scan it."""
        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return []
        return self.scan_source(source, file_path)

    # ------------------------------------------------------------------ #
    # AST checks                                                           #
    # ------------------------------------------------------------------ #

    def _check_subprocess_shell(
        self,
        node: ast.AST,
        file_path: str,
        issues: list[SecurityIssue],
    ) -> None:
        """Detect subprocess calls with shell=True and a variable/f-string arg."""
        if not isinstance(node, ast.Call):
            return
        func = node.func
        if not (
            (isinstance(func, ast.Attribute) and func.attr in ("run", "Popen", "call", "check_output"))
            or (isinstance(func, ast.Name) and func.id in ("Popen", "run"))
        ):
            return
        # Look for shell=True keyword
        shell_true = any(
            isinstance(kw.value, ast.Constant) and kw.value.value is True
            for kw in node.keywords
            if kw.arg == "shell"
        )
        if not shell_true:
            return
        # Check if first arg is not a simple string literal
        args = node.args
        if args and not isinstance(args[0], ast.Constant):
            issues.append(SecurityIssue(
                file=file_path,
                line=node.lineno,
                rule_id="S003",
                severity="high",
                message="`subprocess` called with `shell=True` and a non-literal argument — command injection risk",
                snippet="",
            ))

    def _check_eval(
        self,
        node: ast.AST,
        file_path: str,
        issues: list[SecurityIssue],
    ) -> None:
        """Detect eval() called with a non-literal argument."""
        if not isinstance(node, ast.Call):
            return
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "eval"):
            return
        if node.args and not isinstance(node.args[0], ast.Constant):
            issues.append(SecurityIssue(
                file=file_path,
                line=node.lineno,
                rule_id="S004",
                severity="critical",
                message="`eval()` called with non-constant argument — arbitrary code execution risk",
                snippet="",
            ))
