"""Tests for Task 907 — ProcessRunner + RetryExecutor integration."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lidco.execution.process_runner import ProcessRunner, ProcessResult
from lidco.resilience.retry_executor import RetryConfig


class TestProcessRunnerRetryPolicy:
    """Task 907: retry_policy parameter on ProcessRunner."""

    def test_default_no_retry_policy(self):
        runner = ProcessRunner()
        assert runner._retry_policy is None

    def test_accepts_retry_policy(self):
        cfg = RetryConfig(max_retries=2, base_delay=0.01)
        runner = ProcessRunner(retry_policy=cfg)
        assert runner._retry_policy is cfg

    @patch("lidco.execution.process_runner.subprocess.Popen")
    def test_no_retry_on_success(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = (b"ok\n", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        cfg = RetryConfig(max_retries=2, base_delay=0.001)
        runner = ProcessRunner(retry_policy=cfg)
        result = runner.run("echo hello")
        assert result.ok
        # Popen called exactly once (no retries needed)
        assert mock_popen.call_count == 1

    @patch("lidco.execution.process_runner.subprocess.Popen")
    def test_retries_on_failure_then_succeeds(self, mock_popen):
        fail_proc = MagicMock()
        fail_proc.communicate.return_value = (b"", b"err")
        fail_proc.returncode = 1

        ok_proc = MagicMock()
        ok_proc.communicate.return_value = (b"ok", b"")
        ok_proc.returncode = 0

        mock_popen.side_effect = [fail_proc, ok_proc]

        cfg = RetryConfig(max_retries=2, base_delay=0.001)
        runner = ProcessRunner(retry_policy=cfg)
        result = runner.run("flaky-cmd")
        assert result.ok
        assert mock_popen.call_count == 2

    @patch("lidco.execution.process_runner.subprocess.Popen")
    def test_retries_exhausted_returns_failure(self, mock_popen):
        fail_proc = MagicMock()
        fail_proc.communicate.return_value = (b"", b"err")
        fail_proc.returncode = 1
        mock_popen.return_value = fail_proc

        cfg = RetryConfig(max_retries=1, base_delay=0.001)
        runner = ProcessRunner(retry_policy=cfg)
        result = runner.run("bad-cmd")
        # 1 attempt + 1 retry + 1 final = at least 3 calls
        assert not result.ok
        assert mock_popen.call_count >= 2

    @patch("lidco.execution.process_runner.subprocess.Popen")
    def test_no_retry_when_policy_is_none(self, mock_popen):
        fail_proc = MagicMock()
        fail_proc.communicate.return_value = (b"", b"err")
        fail_proc.returncode = 1
        mock_popen.return_value = fail_proc

        runner = ProcessRunner()
        result = runner.run("fail-cmd")
        assert not result.ok
        assert mock_popen.call_count == 1
