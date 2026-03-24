"""Tests for TurboRunner (T577)."""
import pytest
from lidco.execution.turbo_runner import TurboRunner, RunResult


def test_allowed_pattern_auto_approved():
    runner = TurboRunner(dry_run=True)
    result = runner.run("echo hello")
    assert result.approved
    assert not result.blocked
    assert result.dry_run


def test_blocked_pattern_denied():
    runner = TurboRunner(dry_run=True)
    result = runner.run("rm -rf /tmp/foo")
    assert result.blocked
    assert not result.success


def test_unknown_command_denied_without_callback():
    runner = TurboRunner(dry_run=True)
    result = runner.run("somecustom --flag")
    assert not result.approved
    assert not result.blocked
    assert not result.success


def test_unknown_command_approved_with_callback():
    runner = TurboRunner(confirm_callback=lambda cmd: True, dry_run=True)
    result = runner.run("somecustom --flag")
    assert result.approved
    assert result.success


def test_confirm_callback_denies():
    runner = TurboRunner(confirm_callback=lambda cmd: False, dry_run=True)
    result = runner.run("somecustom --flag")
    assert not result.approved


def test_add_allowed_pattern():
    runner = TurboRunner(allowed_patterns=[], dry_run=True)
    result = runner.run("mycmd arg")
    assert not result.approved
    runner.add_allowed(r"^mycmd\b")
    result = runner.run("mycmd arg")
    assert result.approved


def test_add_blocked_pattern():
    runner = TurboRunner(dry_run=True)
    runner.add_blocked(r"^echo\b")
    result = runner.run("echo hello")
    assert result.blocked


def test_run_many_stops_on_failure():
    runner = TurboRunner(dry_run=True)
    # blocked command will fail; subsequent commands should not run
    results = runner.run_many(["rm -rf /bad", "echo ok"])
    assert len(results) == 1
    assert results[0].blocked


def test_history_accumulates():
    runner = TurboRunner(dry_run=True)
    runner.run("echo a")
    runner.run("echo b")
    assert len(runner.history) == 2


def test_clear_history():
    runner = TurboRunner(dry_run=True)
    runner.run("echo a")
    runner.clear_history()
    assert len(runner.history) == 0


def test_summary():
    runner = TurboRunner(dry_run=True)
    runner.run("echo ok")      # allowed → success
    runner.run("rm -rf /tmp")  # blocked
    s = runner.summary()
    assert s["total"] == 2
    assert s["succeeded"] == 1
    assert s["blocked"] == 1


def test_run_real_command():
    runner = TurboRunner()
    result = runner.run("echo hello")
    assert result.success
    assert "hello" in result.output


def test_blocked_overrides_allowed():
    # If a command matches both allow and block, block wins
    runner = TurboRunner(
        allowed_patterns=[r"^rm\b"],
        blocked_patterns=[r"rm\s+-rf"],
        dry_run=True,
    )
    result = runner.run("rm -rf /tmp")
    assert result.blocked
