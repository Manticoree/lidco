"""Tests for Task 909 — TaskScheduler configurable timeout."""
from __future__ import annotations

import json
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.scheduler.task_scheduler import TaskScheduler, ScheduledTask, TaskRunResult


class TestScheduledTaskTimeout:
    """Task 909: timeout field on ScheduledTask dataclass."""

    def test_default_timeout_is_300(self):
        task = ScheduledTask(
            id="abc",
            name="test",
            command="echo hi",
            schedule="every 10s",
            next_run=time.time(),
        )
        assert task.timeout == 300.0

    def test_custom_timeout(self):
        task = ScheduledTask(
            id="abc",
            name="test",
            command="echo hi",
            schedule="every 10s",
            next_run=time.time(),
            timeout=60.0,
        )
        assert task.timeout == 60.0

    def test_timeout_persists_in_asdict(self):
        task = ScheduledTask(
            id="abc",
            name="test",
            command="echo hi",
            schedule="every 10s",
            next_run=time.time(),
            timeout=120.0,
        )
        d = asdict(task)
        assert d["timeout"] == 120.0


class TestExecuteTaskUsesTimeout:
    """Task 909: _execute_task uses task.timeout instead of hardcoded 300."""

    @patch("lidco.scheduler.task_scheduler.subprocess.run")
    def test_uses_task_timeout(self, mock_run):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = "ok"
        proc.stderr = ""
        mock_run.return_value = proc

        with tempfile.TemporaryDirectory() as tmp:
            sched = TaskScheduler(store_path=Path(tmp) / "tasks.json")
            task = ScheduledTask(
                id="t1",
                name="quick",
                command="echo hi",
                schedule="every 10s",
                next_run=time.time(),
                timeout=42.0,
            )
            result = sched._execute_task(task)
            assert result.success
            # Verify subprocess.run was called with timeout=42.0
            _, kwargs = mock_run.call_args
            assert kwargs["timeout"] == 42.0

    @patch("lidco.scheduler.task_scheduler.subprocess.run")
    def test_timeout_error_message_uses_task_value(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 42)

        with tempfile.TemporaryDirectory() as tmp:
            sched = TaskScheduler(store_path=Path(tmp) / "tasks.json")
            task = ScheduledTask(
                id="t2",
                name="slow",
                command="sleep 999",
                schedule="every 10s",
                next_run=time.time(),
                timeout=42.0,
            )
            result = sched._execute_task(task)
            assert not result.success
            assert "42.0" in result.stderr

    @patch("lidco.scheduler.task_scheduler.subprocess.run")
    def test_default_timeout_still_300(self, mock_run):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""
        mock_run.return_value = proc

        with tempfile.TemporaryDirectory() as tmp:
            sched = TaskScheduler(store_path=Path(tmp) / "tasks.json")
            task = ScheduledTask(
                id="t3",
                name="default",
                command="echo",
                schedule="every 10s",
                next_run=time.time(),
            )
            sched._execute_task(task)
            _, kwargs = mock_run.call_args
            assert kwargs["timeout"] == 300.0
