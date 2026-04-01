"""Tests for Q213 CLI commands."""
from __future__ import annotations

import asyncio
import unittest


def _run(coro):
    return asyncio.run(coro)


def _get_handlers():
    from lidco.cli.commands.q213_cmds import register as _reg

    cmds: dict = {}

    class FakeRegistry:
        def register(self, cmd):
            cmds[cmd.name] = cmd

    _reg(FakeRegistry())
    return cmds


class TestGenDocstringCmd(unittest.TestCase):
    def test_generates_docstring(self):
        cmds = _get_handlers()
        handler = cmds["gen-docstring"].handler
        result = _run(handler("GOOGLE def greet(name: str) -> str:\n    return name"))
        self.assertIn("greet", result)
        self.assertIn("Args:", result)

    def test_empty_args(self):
        cmds = _get_handlers()
        handler = cmds["gen-docstring"].handler
        result = _run(handler(""))
        self.assertIn("Usage:", result)

    def test_invalid_source(self):
        cmds = _get_handlers()
        handler = cmds["gen-docstring"].handler
        result = _run(handler("GOOGLE x = 1"))
        self.assertIn("Error", result)


class TestApiRefCmd(unittest.TestCase):
    def test_scan_source(self):
        cmds = _get_handlers()
        handler = cmds["api-ref"].handler
        src = "def hello():\n    pass"
        result = _run(handler(src))
        self.assertIn("hello", result)

    def test_empty_args(self):
        cmds = _get_handlers()
        handler = cmds["api-ref"].handler
        result = _run(handler(""))
        self.assertIn("Usage:", result)


class TestChangelogCmd(unittest.TestCase):
    def test_generates_changelog(self):
        cmds = _get_handlers()
        handler = cmds["changelog"].handler
        result = _run(handler("feat: add login\nfix: typo"))
        self.assertIn("Added", result)
        self.assertIn("Fixed", result)

    def test_no_conventional(self):
        cmds = _get_handlers()
        handler = cmds["changelog"].handler
        result = _run(handler("random message"))
        self.assertIn("No conventional commits", result)

    def test_empty_args(self):
        cmds = _get_handlers()
        handler = cmds["changelog"].handler
        result = _run(handler(""))
        self.assertIn("Usage:", result)


class TestFindExamplesCmd(unittest.TestCase):
    def test_finds_example(self):
        cmds = _get_handlers()
        handler = cmds["find-examples"].handler
        src = "add def test_it():\n    add(1, 2)\n    assert True"
        result = _run(handler(src))
        # "add" is the target, rest is source
        self.assertIn("add", result)

    def test_missing_args(self):
        cmds = _get_handlers()
        handler = cmds["find-examples"].handler
        result = _run(handler("onlyone"))
        self.assertIn("Usage:", result)


if __name__ == "__main__":
    unittest.main()
