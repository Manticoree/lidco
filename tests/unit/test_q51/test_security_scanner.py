"""Tests for SecurityScanner — Task 348."""

from __future__ import annotations

import pytest

from lidco.analysis.security_scanner import (
    SecurityFinding, SecurityScanner, SecuritySeverity,
)


EVAL_CODE = "result = eval(user_input)\n"
EXEC_CODE = "exec(code_string)\n"
PICKLE_CODE = """\
import pickle
data = pickle.loads(raw_bytes)
"""
YAML_CODE = """\
import yaml
config = yaml.load(stream)
"""
OS_SYSTEM_CODE = "import os\nos.system('rm -rf /')\n"
HASHLIB_MD5 = """\
import hashlib
h = hashlib.md5(data)
"""
ASSERT_CODE = """\
def check_auth(user):
    assert user.is_admin
    return True
"""
SAFE_CODE = """\
def add(a: int, b: int) -> int:
    return a + b
"""
SYNTAX_ERROR = "def broken(:"


class TestSecurityFinding:
    def test_frozen(self):
        f = SecurityFinding(
            rule_id="SEC001", title="eval", severity=SecuritySeverity.CRITICAL,
            file="x.py", line=1, detail="found",
        )
        with pytest.raises((AttributeError, TypeError)):
            f.line = 5  # type: ignore[misc]


class TestSecurityScanner:
    def setup_method(self):
        self.scanner = SecurityScanner()

    def test_empty_source_no_findings(self):
        assert self.scanner.scan("") == []

    def test_safe_code_no_findings(self):
        findings = self.scanner.scan(SAFE_CODE)
        assert len(findings) == 0

    def test_syntax_error_returns_empty(self):
        assert self.scanner.scan(SYNTAX_ERROR) == []

    def test_eval_detected(self):
        findings = self.scanner.scan(EVAL_CODE)
        rule_ids = {f.rule_id for f in findings}
        assert "SEC001" in rule_ids

    def test_eval_is_critical(self):
        findings = self.scanner.scan(EVAL_CODE)
        f = next(f for f in findings if f.rule_id == "SEC001")
        assert f.severity == SecuritySeverity.CRITICAL

    def test_exec_detected(self):
        findings = self.scanner.scan(EXEC_CODE)
        rule_ids = {f.rule_id for f in findings}
        assert "SEC002" in rule_ids

    def test_pickle_loads_detected(self):
        findings = self.scanner.scan(PICKLE_CODE)
        rule_ids = {f.rule_id for f in findings}
        assert "SEC004" in rule_ids

    def test_yaml_load_detected(self):
        findings = self.scanner.scan(YAML_CODE)
        rule_ids = {f.rule_id for f in findings}
        assert "SEC006" in rule_ids

    def test_os_system_detected(self):
        findings = self.scanner.scan(OS_SYSTEM_CODE)
        rule_ids = {f.rule_id for f in findings}
        assert "SEC008" in rule_ids

    def test_hashlib_md5_detected(self):
        findings = self.scanner.scan(HASHLIB_MD5)
        rule_ids = {f.rule_id for f in findings}
        assert "SEC010" in rule_ids

    def test_assert_detected(self):
        findings = self.scanner.scan(ASSERT_CODE)
        rule_ids = {f.rule_id for f in findings}
        assert "SEC011" in rule_ids

    def test_file_path_recorded(self):
        findings = self.scanner.scan(EVAL_CODE, file_path="danger.py")
        assert all(f.file == "danger.py" for f in findings)

    def test_line_number_recorded(self):
        findings = self.scanner.scan(EVAL_CODE)
        f = next(f for f in findings if f.rule_id == "SEC001")
        assert f.line == 1


class TestSecurityScannerFilter:
    def setup_method(self):
        self.scanner = SecurityScanner()

    def test_filter_critical_only(self):
        findings = self.scanner.scan(EVAL_CODE + HASHLIB_MD5)
        critical = self.scanner.filter_by_severity(findings, SecuritySeverity.CRITICAL)
        assert all(f.severity == SecuritySeverity.CRITICAL for f in critical)

    def test_filter_medium_and_above(self):
        findings = self.scanner.scan(EVAL_CODE + HASHLIB_MD5 + ASSERT_CODE)
        medium_up = self.scanner.filter_by_severity(findings, SecuritySeverity.MEDIUM)
        for f in medium_up:
            assert f.severity in (
                SecuritySeverity.MEDIUM, SecuritySeverity.HIGH, SecuritySeverity.CRITICAL
            )

    def test_filter_low_returns_all(self):
        findings = self.scanner.scan(EVAL_CODE)
        result = self.scanner.filter_by_severity(findings, SecuritySeverity.LOW)
        assert len(result) == len(findings)
