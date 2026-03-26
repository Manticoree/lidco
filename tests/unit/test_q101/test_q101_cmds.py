"""Tests for src/lidco/cli/commands/q101_cmds.py."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load_handlers():
    import importlib
    import lidco.cli.commands.q101_cmds as mod
    # Reset state
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


class TestCacheCommand:
    def test_set_and_get(self):
        reg = _load_handlers()
        handler = reg.commands["cache"].handler
        _run(handler("set foo bar"))
        result = _run(handler("get foo"))
        assert "bar" in result

    def test_get_missing(self):
        reg = _load_handlers()
        handler = reg.commands["cache"].handler
        result = _run(handler("get missing_key_xyz"))
        assert "None" in result

    def test_delete(self):
        reg = _load_handlers()
        handler = reg.commands["cache"].handler
        _run(handler("set k v"))
        result = _run(handler("delete k"))
        assert "True" in result

    def test_stats(self):
        reg = _load_handlers()
        handler = reg.commands["cache"].handler
        result = _run(handler("stats"))
        assert "hits" in result

    def test_clear(self):
        reg = _load_handlers()
        handler = reg.commands["cache"].handler
        _run(handler("set x 1"))
        result = _run(handler("clear"))
        assert "cleared" in result.lower()

    def test_keys(self):
        reg = _load_handlers()
        handler = reg.commands["cache"].handler
        _run(handler("set a 1"))
        result = _run(handler("keys"))
        assert "a" in result

    def test_unknown_subcommand(self):
        reg = _load_handlers()
        handler = reg.commands["cache"].handler
        result = _run(handler("badcmd"))
        assert "Unknown" in result

    def test_no_args_returns_usage(self):
        reg = _load_handlers()
        handler = reg.commands["cache"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestPoolCommand:
    def test_stats(self):
        reg = _load_handlers()
        handler = reg.commands["pool"].handler
        result = _run(handler("stats"))
        assert "pool_size" in result

    def test_drain(self):
        reg = _load_handlers()
        handler = reg.commands["pool"].handler
        result = _run(handler("drain"))
        assert "Drained" in result

    def test_info(self):
        reg = _load_handlers()
        handler = reg.commands["pool"].handler
        result = _run(handler("info"))
        assert "size" in result

    def test_default_stats(self):
        reg = _load_handlers()
        handler = reg.commands["pool"].handler
        result = _run(handler(""))
        assert "pool_size" in result


class TestObserverCommand:
    def test_set_and_get(self):
        reg = _load_handlers()
        handler = reg.commands["observer"].handler
        _run(handler("set hello"))
        result = _run(handler("get"))
        assert "hello" in result

    def test_watch(self):
        reg = _load_handlers()
        handler = reg.commands["observer"].handler
        result = _run(handler("watch mylistener"))
        assert "registered" in result.lower()

    def test_unwatch(self):
        reg = _load_handlers()
        handler = reg.commands["observer"].handler
        _run(handler("watch mylistener"))
        result = _run(handler("unwatch mylistener"))
        assert "True" in result or "Removed" in result

    def test_count(self):
        reg = _load_handlers()
        handler = reg.commands["observer"].handler
        result = _run(handler("count"))
        assert "count" in result.lower()

    def test_no_args(self):
        reg = _load_handlers()
        handler = reg.commands["observer"].handler
        result = _run(handler(""))
        assert "Usage" in result


class TestCommandCommand:
    def test_set_and_undo(self):
        reg = _load_handlers()
        handler = reg.commands["command"].handler
        _run(handler("set mykey myval"))
        result = _run(handler("undo"))
        assert "mykey" in result or "Undid" in result

    def test_undo_empty(self):
        reg = _load_handlers()
        handler = reg.commands["command"].handler
        result = _run(handler("undo"))
        assert "Nothing" in result

    def test_redo_empty(self):
        reg = _load_handlers()
        handler = reg.commands["command"].handler
        result = _run(handler("redo"))
        assert "Nothing" in result

    def test_history(self):
        reg = _load_handlers()
        handler = reg.commands["command"].handler
        _run(handler("set a 1"))
        result = _run(handler("history"))
        assert "a" in result or "set" in result

    def test_clear_history(self):
        reg = _load_handlers()
        handler = reg.commands["command"].handler
        _run(handler("set a 1"))
        result = _run(handler("clear"))
        assert "cleared" in result.lower()

    def test_delete_command(self):
        reg = _load_handlers()
        handler = reg.commands["command"].handler
        _run(handler("set x hello"))
        result = _run(handler("delete x"))
        assert "Executed" in result

    def test_state_display(self):
        reg = _load_handlers()
        handler = reg.commands["command"].handler
        _run(handler("set foo bar"))
        result = _run(handler("state"))
        assert "foo" in result

    def test_unknown_subcommand(self):
        reg = _load_handlers()
        handler = reg.commands["command"].handler
        result = _run(handler("badcmd"))
        assert "Unknown" in result
