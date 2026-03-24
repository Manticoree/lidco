"""Tests for pipeline/schedule CLI commands (T515)."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

import lidco.cli.commands.pipeline_cmds as pcmds
from lidco.cli.commands.pipeline_cmds import (
    pipeline_status_handler,
    pipeline_run_handler,
    schedule_add_handler,
    schedule_remove_handler,
    schedule_list_handler,
    schedule_tick_handler,
    register_pipeline_commands,
)


def run(coro):
    return asyncio.run(coro)


# ---- /pipeline status ----

def test_pipeline_status_no_results():
    pcmds._last_results = []
    result = run(pipeline_status_handler())
    assert "No pipeline results" in result


def test_pipeline_status_with_results():
    r = MagicMock()
    r.issue_number = 42
    r.status = "merged"
    r.security_passed = True
    r.branch = "fix/42"
    pcmds._last_results = [r]
    result = run(pipeline_status_handler())
    assert "#42" in result
    assert "merged" in result
    pcmds._last_results = []


# ---- /pipeline run ----

def test_pipeline_run_no_issues():
    mock_pipeline = MagicMock()
    mock_pipeline.poll_and_run.return_value = []

    with patch("lidco.cli.commands.pipeline_cmds.IssueToPRPipeline", return_value=mock_pipeline, create=True), \
         patch("lidco.cli.commands.pipeline_cmds.PipelineConfig", create=True):
        result = run(pipeline_run_handler())
    assert "No new issues" in result


def test_pipeline_run_import_error_returns_error_string():
    with patch.dict("sys.modules", {"lidco.pipelines.issue_to_pr": None}):
        # Force import error path
        result = run(pipeline_run_handler())
    assert "failed" in result.lower() or "unavailable" in result.lower() or "Pipeline" in result


# ---- /schedule add ----

def _make_runner():
    runner = MagicMock()
    runner.add_task.return_value = None
    runner.remove_task.return_value = True
    runner.list_tasks.return_value = []
    runner.tick.return_value = []
    return runner


def test_schedule_add_valid(monkeypatch):
    runner = _make_runner()
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_add_handler('daily "0 8 * * *" run tests'))
    assert "daily" in result
    assert runner.add_task.called


def test_schedule_add_missing_args(monkeypatch):
    runner = _make_runner()
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_add_handler("only-one-arg"))
    assert "Usage" in result


def test_schedule_add_no_runner(monkeypatch):
    monkeypatch.setattr(pcmds, "_cron_runner", None)
    with patch("lidco.cli.commands.pipeline_cmds._get_cron_runner", return_value=None):
        result = run(schedule_add_handler('t "* * * * *" do something'))
    assert "unavailable" in result.lower()


# ---- /schedule remove ----

def test_schedule_remove_success(monkeypatch):
    runner = _make_runner()
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_remove_handler("daily"))
    assert "removed" in result


def test_schedule_remove_not_found(monkeypatch):
    runner = _make_runner()
    runner.remove_task.return_value = False
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_remove_handler("missing"))
    assert "not found" in result


def test_schedule_remove_empty_args(monkeypatch):
    runner = _make_runner()
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_remove_handler(""))
    assert "Usage" in result


# ---- /schedule list ----

def test_schedule_list_empty(monkeypatch):
    runner = _make_runner()
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_list_handler())
    assert "No scheduled tasks" in result


def test_schedule_list_with_tasks(monkeypatch):
    task = MagicMock()
    task.name = "nightly"
    task.enabled = True
    task.cron_expr = "0 2 * * *"
    task.instruction = "cleanup"
    runner = _make_runner()
    runner.list_tasks.return_value = [task]
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_list_handler())
    assert "nightly" in result


# ---- /schedule tick ----

def test_schedule_tick_no_due(monkeypatch):
    runner = _make_runner()
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_tick_handler())
    assert "No tasks were due" in result


def test_schedule_tick_with_results(monkeypatch):
    r = MagicMock()
    r.task_name = "nightly"
    r.success = True
    r.error = None
    runner = _make_runner()
    runner.tick.return_value = [r]
    monkeypatch.setattr(pcmds, "_cron_runner", runner)
    result = run(schedule_tick_handler())
    assert "nightly" in result


# ---- register ----

def test_register_pipeline_commands():
    registry = MagicMock()
    register_pipeline_commands(registry)
    assert registry.register.call_count >= 6
