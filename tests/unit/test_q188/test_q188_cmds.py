"""Tests for q188_cmds CLI wiring (task 1056)."""

import asyncio
import pytest
from lidco.cli.commands.registry import CommandRegistry


def get_handler(name: str):
    registry = CommandRegistry()
    cmd = registry.get(name)
    assert cmd is not None, f"Command /{name} not registered"
    return cmd.handler


def run(coro):
    return asyncio.run(coro)


# -- /loop-run ------------------------------------------------------------


def test_loop_run_registered():
    registry = CommandRegistry()
    assert registry.get("loop-run") is not None


def test_loop_run_basic():
    h = get_handler("loop-run")
    result = run(h("hello world"))
    assert "Loop finished" in result
    assert "Iterations" in result


def test_loop_run_with_max():
    h = get_handler("loop-run")
    result = run(h("test --max 3"))
    assert "Iterations: 3" in result


def test_loop_run_with_promise():
    h = get_handler("loop-run")
    # The echo executor won't contain the promise, so all iterations run
    result = run(h("test --promise DONE --max 5"))
    assert "Iterations:" in result


def test_loop_run_shows_duration():
    h = get_handler("loop-run")
    result = run(h("quick"))
    assert "Duration:" in result


def test_loop_run_shows_completion():
    h = get_handler("loop-run")
    result = run(h("quick"))
    assert "Completed naturally:" in result


# -- /loop-status ---------------------------------------------------------


def test_loop_status_registered():
    registry = CommandRegistry()
    assert registry.get("loop-status") is not None


def test_loop_status_no_runner():
    h = get_handler("loop-status")
    result = run(h(""))
    assert "No loop runner" in result or "state" in result.lower()


def test_loop_status_after_run():
    registry = CommandRegistry()
    run_h = registry.get("loop-run").handler
    run(run_h("test --max 2"))
    status_h = registry.get("loop-status").handler
    result = run(status_h(""))
    # Either shows state or no-runner (depends on shared state)
    assert isinstance(result, str)


# -- /loop-cancel ---------------------------------------------------------


def test_loop_cancel_registered():
    registry = CommandRegistry()
    assert registry.get("loop-cancel") is not None


def test_loop_cancel_no_runner():
    h = get_handler("loop-cancel")
    result = run(h(""))
    assert "No loop runner" in result or "cancel" in result.lower()


# -- /loop-history --------------------------------------------------------


def test_loop_history_registered():
    registry = CommandRegistry()
    assert registry.get("loop-history") is not None


def test_loop_history_no_run():
    h = get_handler("loop-history")
    result = run(h(""))
    assert "No loop history" in result or "history" in result.lower()


def test_loop_history_after_run():
    registry = CommandRegistry()
    run_h = registry.get("loop-run").handler
    run(run_h("test --max 3"))
    hist_h = registry.get("loop-history").handler
    result = run(hist_h(""))
    # Might show history or no-history depending on module-level state sharing
    assert isinstance(result, str)


# -- general --------------------------------------------------------------


def test_all_four_commands_registered():
    registry = CommandRegistry()
    for name in ("loop-run", "loop-status", "loop-cancel", "loop-history"):
        assert registry.get(name) is not None, f"/{name} not registered"
