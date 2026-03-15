"""Tests for SecurityScanner — Task 414."""

from __future__ import annotations

import pytest

from lidco.proactive.security_scanner import SecurityIssue, SecurityScanner


HARDCODED_PASSWORD = """\
password = "supersecret123"
"""

HARDCODED_TOKEN = """\
api_key = "sk-1234567890abcdef"
"""

SQL_FSTRING = """\
query = f"SELECT * FROM users WHERE id = {user_id}"
"""

SUBPROCESS_SHELL_VAR = """\
import subprocess
cmd = user_input
subprocess.run(cmd, shell=True)
"""

EVAL_DYNAMIC = """\
eval(user_input)
"""

OS_SYSTEM_CALL = """\
import os
os.system("ls -la")
"""

SUBPROCESS_SHELL_LITERAL = """\
import subprocess
subprocess.run("ls -la", shell=True)
"""

CLEAN_CODE = """\
import subprocess
subprocess.run(["ls", "-la"])
"""

SYNTAX_ERROR = "def bad(:"

MULTIPLE_ISSUES = """\
import os
password = "hunter2"
os.system("rm -rf /")
eval(user_code)
"""


class TestSecurityIssue:

    def test_fields(self) -> None:
        issue = SecurityIssue(
            file="f.py", line=1, rule_id="S001",
            severity="critical", message="secret found", snippet="password = 'x'",
        )
        assert issue.file == "f.py"
        assert issue.rule_id == "S001"
        assert issue.severity == "critical"

    def test_frozen(self) -> None:
        issue = SecurityIssue(file="f.py", line=1, rule_id="S001",
                              severity="critical", message="msg", snippet="")
        with pytest.raises((AttributeError, TypeError)):
            issue.severity = "low"  # type: ignore[misc]


class TestSecurityScanner:

    def setup_method(self) -> None:
        self.scanner = SecurityScanner()

    def test_hardcoded_password(self) -> None:
        issues = self.scanner.scan_source(HARDCODED_PASSWORD, "f.py")
        rule_ids = [i.rule_id for i in issues]
        assert "S001" in rule_ids

    def test_hardcoded_token(self) -> None:
        issues = self.scanner.scan_source(HARDCODED_TOKEN, "f.py")
        rule_ids = [i.rule_id for i in issues]
        assert "S001" in rule_ids

    def test_sql_injection_fstring(self) -> None:
        issues = self.scanner.scan_source(SQL_FSTRING, "f.py")
        rule_ids = [i.rule_id for i in issues]
        assert "S002" in rule_ids

    def test_subprocess_shell_variable(self) -> None:
        issues = self.scanner.scan_source(SUBPROCESS_SHELL_VAR, "f.py")
        rule_ids = [i.rule_id for i in issues]
        assert "S003" in rule_ids

    def test_eval_dynamic_input(self) -> None:
        issues = self.scanner.scan_source(EVAL_DYNAMIC, "f.py")
        rule_ids = [i.rule_id for i in issues]
        assert "S004" in rule_ids

    def test_os_system_call(self) -> None:
        issues = self.scanner.scan_source(OS_SYSTEM_CALL, "f.py")
        rule_ids = [i.rule_id for i in issues]
        assert "S005" in rule_ids

    def test_subprocess_shell_literal_no_s003(self) -> None:
        """shell=True with a literal string should NOT trigger S003."""
        issues = self.scanner.scan_source(SUBPROCESS_SHELL_LITERAL, "f.py")
        rule_ids = [i.rule_id for i in issues]
        assert "S003" not in rule_ids

    def test_clean_code_no_issues(self) -> None:
        issues = self.scanner.scan_source(CLEAN_CODE, "f.py")
        assert issues == []

    def test_syntax_error_returns_partial(self) -> None:
        # Line-based scans should still run; AST scan is skipped
        issues = self.scanner.scan_source(SYNTAX_ERROR, "f.py")
        # No crash — could be empty or have line-based hits
        assert isinstance(issues, list)

    def test_multiple_issues(self) -> None:
        issues = self.scanner.scan_source(MULTIPLE_ISSUES, "f.py")
        rule_ids = {i.rule_id for i in issues}
        assert len(rule_ids) >= 2

    def test_scan_missing_file(self) -> None:
        issues = self.scanner.scan_file("/nonexistent/path.py")
        assert issues == []

    def test_issue_has_file_and_line(self) -> None:
        issues = self.scanner.scan_source(HARDCODED_PASSWORD, "myfile.py")
        assert len(issues) >= 1
        assert issues[0].file == "myfile.py"
        assert issues[0].line >= 1
