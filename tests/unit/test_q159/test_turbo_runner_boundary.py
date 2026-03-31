"""Tests for Task 908 — TurboRunner + ErrorBoundary integration."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lidco.execution.turbo_runner import TurboRunner, RunResult


class TestTurboRunnerErrorBoundary:
    """Task 908: ErrorBoundary wraps command execution in TurboRunner."""

    def test_last_errors_starts_empty(self):
        runner = TurboRunner(dry_run=True)
        assert runner.last_errors == []

    def test_boundary_attribute_exists(self):
        runner = TurboRunner(dry_run=True)
        assert runner._boundary is not None

    def test_dry_run_no_boundary_errors(self):
        runner = TurboRunner(dry_run=True)
        result = runner.run("echo hello")
        assert result.success
        assert runner.last_errors == []

    @patch("lidco.execution.turbo_runner.subprocess.run")
    def test_normal_execution_goes_through_boundary(self, mock_run):
        proc = MagicMock()
        proc.stdout = "output"
        proc.stderr = ""
        proc.returncode = 0
        mock_run.return_value = proc

        runner = TurboRunner(allowed_patterns=[r"^echo\b"])
        result = runner.run("echo test")
        assert result.success
        assert result.stdout == "output"

    @patch("lidco.execution.turbo_runner.subprocess.run")
    def test_boundary_catches_unexpected_exception(self, mock_run):
        mock_run.side_effect = OSError("Permission denied")

        runner = TurboRunner(allowed_patterns=[r"^bad\b"])
        result = runner.run("bad command")
        # ErrorBoundary catches the OSError; result should be the default
        assert result.returncode == -1
        assert not result.success
        # last_errors should have been populated
        assert len(runner.last_errors) >= 1
        assert runner.last_errors[0]["error_type"] == "OSError"

    @patch("lidco.execution.turbo_runner.subprocess.run")
    def test_timeout_handled_inside_boundary(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 60)

        runner = TurboRunner(allowed_patterns=[r"^slow\b"])
        result = runner.run("slow cmd")
        # TimeoutExpired is caught by the inner try/except, not by boundary
        assert result.returncode == -1
        assert "timed out" in result.stderr

    def test_blocked_command_no_boundary_interaction(self):
        runner = TurboRunner()
        result = runner.run("sudo rm -rf /")
        assert result.blocked
        assert runner.last_errors == []
