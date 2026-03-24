"""Tests for /watch and /architect CLI commands (T527)."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

import lidco.cli.commands.watch_cmds as wcmds
from lidco.cli.commands.watch_cmds import (
    watch_start_handler, watch_stop_handler, watch_status_handler,
    architect_handler, register_watch_commands, register_architect_commands,
)


def run(coro):
    return asyncio.run(coro)


def reset_trigger():
    wcmds._watch_trigger = None


# ---- /watch start ----

def test_watch_start_creates_trigger(tmp_path, monkeypatch):
    reset_trigger()
    mock_trigger = MagicMock()
    mock_trigger.running = False
    with patch("lidco.cli.commands.watch_cmds.WatchAgentTrigger", return_value=mock_trigger, create=True):
        result = run(watch_start_handler())
    assert "started" in result.lower() or "Watch" in result


def test_watch_start_already_running(monkeypatch):
    mock = MagicMock()
    mock.running = True
    wcmds._watch_trigger = mock
    result = run(watch_start_handler())
    assert "already running" in result
    reset_trigger()


# ---- /watch stop ----

def test_watch_stop_not_running():
    reset_trigger()
    result = run(watch_stop_handler())
    assert "not running" in result.lower()


def test_watch_stop_running(monkeypatch):
    mock = MagicMock()
    mock.running = True
    wcmds._watch_trigger = mock
    result = run(watch_stop_handler())
    assert "stopped" in result.lower()
    mock.stop.assert_called_once()
    reset_trigger()


# ---- /watch status ----

def test_watch_status_inactive():
    reset_trigger()
    result = run(watch_status_handler())
    assert "inactive" in result.lower() or "never" in result.lower()


def test_watch_status_running(monkeypatch):
    mock = MagicMock()
    mock.running = True
    wcmds._watch_trigger = mock
    result = run(watch_status_handler())
    assert "running" in result.lower()
    reset_trigger()


def test_watch_status_stopped(monkeypatch):
    mock = MagicMock()
    mock.running = False
    wcmds._watch_trigger = mock
    result = run(watch_status_handler())
    assert "stopped" in result.lower()
    reset_trigger()


# ---- /architect ----

def test_architect_empty_args():
    result = run(architect_handler(""))
    assert "Usage" in result


def test_architect_with_task():
    result = run(architect_handler("add logging to main.py"))
    assert isinstance(result, str)
    assert len(result) > 0


# ---- registration ----

def test_register_watch_commands():
    registry = MagicMock()
    register_watch_commands(registry)
    assert registry.register.call_count == 3


def test_register_architect_commands():
    registry = MagicMock()
    register_architect_commands(registry)
    assert registry.register.call_count == 1
