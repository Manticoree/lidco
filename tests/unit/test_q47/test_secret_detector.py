"""Tests for SecretDetector — Task 324."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.security.secret_detector import SecretDetector, SecretFinding, SecretRule


# ---------------------------------------------------------------------------
# scan_text()
# ---------------------------------------------------------------------------

class TestSecretDetectorScanText:
    def test_detects_openai_key(self):
        detector = SecretDetector()
        text = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz1234"'
        findings = detector.scan_text(text)
        assert len(findings) >= 1
        assert any("openai" in f.rule_id.lower() or "api" in f.rule_id for f in findings)

    def test_detects_aws_access_key(self):
        detector = SecretDetector()
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7ABCDEFG"  # no 'example' substring
        findings = detector.scan_text(text)
        assert any("aws" in f.rule_id.lower() for f in findings)

    def test_detects_password(self):
        detector = SecretDetector()
        text = 'DB_PASSWORD = "supersecretpassword123"'
        findings = detector.scan_text(text)
        assert len(findings) >= 1

    def test_detects_github_token(self):
        detector = SecretDetector()
        token = "ghp_" + "A" * 36
        findings = detector.scan_text(f'token = "{token}"')
        assert any("github" in f.rule_id.lower() for f in findings)

    def test_detects_connection_string(self):
        detector = SecretDetector()
        text = "DB_URL = postgresql://user:password@localhost/mydb"
        findings = detector.scan_text(text)
        assert any("connection" in f.rule_id.lower() for f in findings)

    def test_ignores_example_lines(self):
        detector = SecretDetector()
        text = "# example: api_key = sk-abcdefghijklmnopqrstuvwxyz"
        findings = detector.scan_text(text)
        assert len(findings) == 0

    def test_returns_line_number(self):
        detector = SecretDetector()
        text = "safe line\napi_key = sk-abcdefghijklmnopqrstuvwx12345\nmore safe"
        findings = detector.scan_text(text)
        assert any(f.line_number == 2 for f in findings)

    def test_no_findings_on_clean_text(self):
        detector = SecretDetector()
        text = "x = 1\nprint('hello')\nreturn result"
        findings = detector.scan_text(text)
        assert len(findings) == 0

    def test_file_path_stored_in_finding(self):
        detector = SecretDetector()
        text = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz12345"'
        findings = detector.scan_text(text, file_path="config.py")
        assert all(f.file_path == "config.py" for f in findings)


# ---------------------------------------------------------------------------
# SecretFinding.redacted
# ---------------------------------------------------------------------------

class TestSecretFindingRedacted:
    def test_redacted_masks_long_tokens(self):
        finding = SecretFinding(
            rule_id="test",
            description="test",
            severity="HIGH",
            line_number=1,
            line='api_key = "sk-abcdefghijklmnopqrstuvwxyz"',
        )
        redacted = finding.redacted
        assert "****" in redacted

    def test_redacted_preserves_short_tokens(self):
        finding = SecretFinding(
            rule_id="test",
            description="test",
            severity="HIGH",
            line_number=1,
            line="x = 1",
        )
        # short tokens shouldn't be redacted
        assert finding.redacted == "x = 1"


# ---------------------------------------------------------------------------
# scan_file()
# ---------------------------------------------------------------------------

class TestSecretDetectorScanFile:
    def test_scan_file_with_secret(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text('SECRET_KEY = "abcdefghijklmnopqrstuvwxyz"\n', encoding="utf-8")
        detector = SecretDetector()
        findings = detector.scan_file(f)
        assert len(findings) >= 1
        assert findings[0].file_path == str(f)

    def test_scan_file_skips_pyc(self, tmp_path):
        f = tmp_path / "module.pyc"
        f.write_bytes(b"binary")
        detector = SecretDetector()
        findings = detector.scan_file(f)
        assert findings == []

    def test_scan_missing_file_returns_empty(self):
        detector = SecretDetector()
        findings = detector.scan_file("/nonexistent/path/config.py")
        assert findings == []


# ---------------------------------------------------------------------------
# scan_diff()
# ---------------------------------------------------------------------------

class TestSecretDetectorScanDiff:
    def test_only_scans_added_lines(self):
        detector = SecretDetector()
        diff = (
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "-api_key = 'old_key'\n"
            "+api_key = 'sk-newabcdefghijklmnopqrstuvwxyz12'\n"
            " context_line\n"
        )
        findings = detector.scan_diff(diff)
        # Should detect in added line (+) not in removed line (-)
        assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Custom rules
# ---------------------------------------------------------------------------

class TestSecretDetectorCustomRules:
    def test_custom_rule_detected(self):
        import re
        rule = SecretRule(
            rule_id="custom-token",
            pattern=re.compile(r"MYTOKEN_[A-Z0-9]{16}"),
            description="Custom token",
        )
        detector = SecretDetector(rules=[rule])
        text = "auth = MYTOKEN_ABCDEF1234567890"
        findings = detector.scan_text(text)
        assert len(findings) == 1
        assert findings[0].rule_id == "custom-token"
