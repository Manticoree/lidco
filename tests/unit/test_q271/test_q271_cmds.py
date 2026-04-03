"""Tests for Q271 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q271_cmds import register, _state
from lidco.cli.commands.registry import CommandRegistry


def _run(coro):
    return asyncio.run(coro)


def _make_registry():
    reg = object.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    register(reg)
    return reg


class TestShortcutsCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()

    def test_list_empty(self):
        reg = _make_registry()
        result = _run(reg.get("shortcuts").handler("list"))
        self.assertIn("No shortcuts registered", result)

    def test_add_and_find(self):
        reg = _make_registry()
        result = _run(reg.get("shortcuts").handler("add ctrl+s save"))
        self.assertIn("Registered", result)
        result = _run(reg.get("shortcuts").handler("find save"))
        self.assertIn("ctrl+s", result)

    def test_remove(self):
        reg = _make_registry()
        _run(reg.get("shortcuts").handler("add ctrl+s save"))
        result = _run(reg.get("shortcuts").handler("remove ctrl+s"))
        self.assertIn("Removed", result)

    def test_usage(self):
        reg = _make_registry()
        result = _run(reg.get("shortcuts").handler("badcmd"))
        self.assertIn("Usage", result)


class TestProfileCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()

    def test_list(self):
        reg = _make_registry()
        result = _run(reg.get("shortcut-profile").handler("list"))
        self.assertIn("default", result)

    def test_activate(self):
        reg = _make_registry()
        result = _run(reg.get("shortcut-profile").handler("activate vim"))
        self.assertIn("Activated", result)

    def test_create(self):
        reg = _make_registry()
        result = _run(reg.get("shortcut-profile").handler("create myprof"))
        self.assertIn("Created", result)


class TestPaletteCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()

    def test_register_and_search(self):
        reg = _make_registry()
        _run(reg.get("palette").handler("register save Save-file"))
        result = _run(reg.get("palette").handler("search save"))
        self.assertIn("save", result)

    def test_recent_empty(self):
        reg = _make_registry()
        result = _run(reg.get("palette").handler("recent"))
        self.assertIn("No recent", result)


class TestTrainCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()

    def test_quiz_no_shortcuts(self):
        reg = _make_registry()
        result = _run(reg.get("shortcut-train").handler("quiz"))
        self.assertIn("No shortcuts", result)

    def test_accuracy(self):
        reg = _make_registry()
        result = _run(reg.get("shortcut-train").handler("accuracy"))
        self.assertIn("accuracy", result.lower())


if __name__ == "__main__":
    unittest.main()
