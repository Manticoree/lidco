"""Tests for Q277 CLI commands."""
from __future__ import annotations

import asyncio
import unittest


def _run(coro):
    return asyncio.run(coro)


def _make_registry():
    from lidco.cli.commands.q277_cmds import register

    class FakeRegistry:
        def __init__(self):
            self.commands = {}
        def register(self, cmd):
            self.commands[cmd.name] = cmd

    reg = FakeRegistry()
    register(reg)
    return reg


class TestAnnotateCommand(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()
        self.handler = self.reg.commands["annotate"].handler

    def test_add(self):
        result = _run(self.handler("add f.py 10 hello"))
        self.assertIn("Added annotation", result)

    def test_add_missing_args(self):
        result = _run(self.handler("add f.py"))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        result = _run(self.handler("list"))
        self.assertIn("No annotations", result)

    def test_remove_missing(self):
        result = _run(self.handler("remove xyz"))
        self.assertIn("not found", result)

    def test_clear(self):
        _run(self.handler("add f.py 1 x"))
        result = _run(self.handler("clear"))
        self.assertIn("Cleared", result)

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)


class TestMarkersCommand(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()
        self.handler = self.reg.commands["markers"].handler

    def test_list(self):
        result = _run(self.handler("list"))
        self.assertIn("TODO", result)

    def test_add_custom(self):
        result = _run(self.handler("add HACK HACK 1"))
        self.assertIn("Registered", result)

    def test_remove_builtin_fails(self):
        result = _run(self.handler("remove TODO"))
        self.assertIn("Cannot remove", result)

    def test_scan(self):
        result = _run(self.handler("scan TODO: fix this"))
        self.assertIn("TODO", result)

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)


class TestOverlayCommand(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()
        self.handler = self.reg.commands["annotation-overlay"].handler

    def test_render(self):
        result = _run(self.handler("test.py"))
        self.assertIn("test.py", result)

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)


class TestSearchAnnotationsCommand(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()
        self.handler = self.reg.commands["search-annotations"].handler

    def test_stats_empty(self):
        result = _run(self.handler("stats"))
        self.assertIn("Total: 0", result)

    def test_export_empty(self):
        result = _run(self.handler("export"))
        self.assertIn("[]", result)

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
