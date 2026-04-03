"""Tests for Q273 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _make_registry():
    registry = MagicMock()
    registered = {}

    def register_async(name, desc, handler):
        registered[name] = handler

    registry.register_async.side_effect = register_async
    registry._handlers = registered
    return registry


def _get(registry, name):
    return registry._handlers[name]


class TestRegisterQ273(unittest.TestCase):
    def test_all_commands_registered(self):
        from lidco.cli.commands.q273_cmds import register_q273_commands

        r = _make_registry()
        register_q273_commands(r)
        assert "widgets" in r._handlers
        assert "file-picker" in r._handlers
        assert "diff-view" in r._handlers
        assert "progress-view" in r._handlers


class TestWidgetsCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q273_cmds import register_q273_commands

        r = _make_registry()
        register_q273_commands(r)
        return _get(r, "widgets")

    def test_no_args_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        assert "Usage" in result

    def test_list_empty(self):
        h = self._handler()
        result = asyncio.run(h("list"))
        assert "No widgets" in result


class TestFilePickerCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q273_cmds import register_q273_commands

        r = _make_registry()
        register_q273_commands(r)
        return _get(r, "file-picker")

    def test_no_args_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        assert "Usage" in result

    def test_bookmark(self):
        h = self._handler()
        result = asyncio.run(h("bookmark /tmp/a"))
        assert "Bookmarked" in result

    def test_recent_empty(self):
        h = self._handler()
        result = asyncio.run(h("recent"))
        assert "No recent" in result


class TestDiffViewCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q273_cmds import register_q273_commands

        r = _make_registry()
        register_q273_commands(r)
        return _get(r, "diff-view")

    def test_no_args_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        assert "Usage" in result

    def test_set_and_hunks(self):
        h = self._handler()
        result = asyncio.run(h('set "old line" "new line"'))
        assert "hunk" in result.lower()


class TestProgressViewCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q273_cmds import register_q273_commands

        r = _make_registry()
        register_q273_commands(r)
        return _get(r, "progress-view")

    def test_no_args_usage(self):
        h = self._handler()
        result = asyncio.run(h(""))
        assert "Usage" in result

    def test_add_task(self):
        h = self._handler()
        result = asyncio.run(h("add Build project"))
        assert "Task added" in result
        assert "Build project" in result


if __name__ == "__main__":
    unittest.main()
