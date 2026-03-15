"""Tests for Q42 — TestRunner (Task 286)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.tdd.runner import TestCase, TestRunResult, TestRunner


class TestTestRunResult:
    def test_passed_true_when_no_failures(self):
        r = TestRunResult(passed=True, total=5, n_passed=5)
        assert r.passed is True

    def test_summary_green(self):
        r = TestRunResult(passed=True, total=3, n_passed=3)
        assert "GREEN" in r.summary

    def test_summary_red(self):
        r = TestRunResult(passed=False, total=3, n_passed=2, n_failed=1)
        assert "RED" in r.summary

    def test_summary_with_error(self):
        r = TestRunResult(passed=False, error="timeout")
        assert "timeout" in r.summary

    def test_summary_shows_first_failure(self):
        r = TestRunResult(
            passed=False, total=1, n_failed=1,
            cases=[TestCase(nodeid="tests/test_x.py::test_foo", outcome="failed", message="AssertionError")]
        )
        assert "test_foo" in r.summary


class TestTestRunnerParsers:
    def test_parse_stdout_passed(self):
        runner = TestRunner()
        output = "3 passed in 0.5s"
        result = runner._parse_stdout(output, returncode=0)
        assert result.passed is True
        assert result.n_passed == 3

    def test_parse_stdout_failed(self):
        runner = TestRunner()
        output = "2 passed, 1 failed in 1.0s\nFAILED tests/test_x.py::test_a - AssertionError"
        result = runner._parse_stdout(output, returncode=1)
        assert result.passed is False
        assert result.n_failed == 1
        assert len(result.cases) == 1
        assert result.cases[0].outcome == "failed"

    def test_parse_stdout_timeout(self):
        runner = TestRunner()
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pytest", 60)):
            result = runner.run()
        assert result.passed is False
        assert "timed out" in result.error.lower()

    def test_parse_json_report(self, tmp_path):
        runner = TestRunner(project_dir=tmp_path)
        report = {
            "summary": {"passed": 2, "failed": 1},
            "tests": [
                {"nodeid": "a::b", "outcome": "passed"},
                {"nodeid": "a::c", "outcome": "failed", "call": {"longrepr": "AssertionError"}},
            ]
        }
        report_path = tmp_path / ".lidco" / "_tdd_pytest_report.json"
        report_path.parent.mkdir(parents=True)
        report_path.write_text(json.dumps(report))
        result = runner._parse_json_report(report_path, "")
        assert result.n_passed == 2
        assert result.n_failed == 1
        assert result.passed is False

    def test_parse_json_report_all_passed(self, tmp_path):
        runner = TestRunner(project_dir=tmp_path)
        report = {"summary": {"passed": 4, "failed": 0}, "tests": []}
        path = tmp_path / ".lidco" / "_tdd_pytest_report.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(report))
        result = runner._parse_json_report(path, "")
        assert result.passed is True


class TestTestRunnerRun:
    def test_run_uses_subprocess(self, tmp_path):
        runner = TestRunner(project_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.stdout = "1 passed in 0.1s"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            result = runner.run()
        assert result.passed is True
