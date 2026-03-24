"""Tests for SecurityGate — T490."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.review.security_gate import GateResult, SecurityFinding, SecurityGate


class TestSecurityGate:
    def test_clean_file_passes(self, tmp_path):
        (tmp_path / "a.py").write_text("def add(x, y): return x + y\n")
        gate = SecurityGate(project_dir=tmp_path)
        result = gate.check(["a.py"])
        assert result.passed

    def test_hardcoded_api_key_fails(self, tmp_path):
        (tmp_path / "b.py").write_text('api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"\n')
        gate = SecurityGate(project_dir=tmp_path)
        result = gate.check(["b.py"])
        assert not result.passed
        assert result.blocked_reason is not None

    def test_hardcoded_password_detected(self, tmp_path):
        (tmp_path / "c.py").write_text('password = "mysecretpass"\n')
        gate = SecurityGate(project_dir=tmp_path)
        result = gate.check(["c.py"])
        findings = [f for f in result.findings if "password" in f.description.lower()]
        assert len(findings) >= 1

    def test_eval_user_input_detected(self, tmp_path):
        (tmp_path / "d.py").write_text('result = eval(user_input)\n')
        gate = SecurityGate(project_dir=tmp_path)
        result = gate.check(["d.py"])
        high = [f for f in result.findings if f.severity == "high"]
        assert len(high) >= 1

    def test_missing_file_skipped(self, tmp_path):
        gate = SecurityGate(project_dir=tmp_path)
        result = gate.check(["nonexistent.py"])
        assert result.passed  # no file = no findings

    def test_gate_result_fields(self):
        r = GateResult(passed=True, findings=[], blocked_reason=None)
        assert r.passed

    def test_finding_fields(self):
        f = SecurityFinding(file="x.py", line=5, severity="critical", description="leaked key")
        assert f.severity == "critical"

    def test_multiple_files(self, tmp_path):
        (tmp_path / "clean.py").write_text("x = 1\n")
        (tmp_path / "dirty.py").write_text('api_key = "sk-abcdefghijklmnopqrstuvwxyz"\n')
        gate = SecurityGate(project_dir=tmp_path)
        result = gate.check(["clean.py", "dirty.py"])
        assert not result.passed
