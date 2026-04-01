"""Tests for Q206 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q206_cmds as q206_mod


def _setup():
    """Reset module state and register commands into a fresh registry."""
    q206_mod._state.clear()
    from lidco.cli.commands.registry import CommandRegistry

    cr = CommandRegistry.__new__(CommandRegistry)
    cr._commands = {}
    cr._session = None
    q206_mod.register(cr)
    return cr


class TestScreenshotCmd(unittest.TestCase):
    def setUp(self):
        cr = _setup()
        self.handler = cr._commands["screenshot"].handler

    def test_capture_full(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("1920", result)
        self.assertIn("1080", result)

    def test_capture_region(self):
        result = asyncio.run(self.handler("region 10 20 200 100"))
        self.assertIn("200x100", result)

    def test_history(self):
        asyncio.run(self.handler(""))
        result = asyncio.run(self.handler("history"))
        self.assertIn("1 screenshot(s)", result)


class TestClickCmd(unittest.TestCase):
    def setUp(self):
        cr = _setup()
        self.handler = cr._commands["click"].handler

    def test_click(self):
        result = asyncio.run(self.handler("100 200"))
        self.assertIn("100", result)
        self.assertIn("200", result)

    def test_click_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestTypeTextCmd(unittest.TestCase):
    def setUp(self):
        cr = _setup()
        self.handler = cr._commands["type-text"].handler

    def test_type(self):
        result = asyncio.run(self.handler("hello world"))
        self.assertIn("hello world", result)

    def test_type_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestVisualTestCmd(unittest.TestCase):
    def setUp(self):
        cr = _setup()
        self.handler = cr._commands["visual-test"].handler

    def test_summary_no_tests(self):
        result = asyncio.run(self.handler("summary"))
        self.assertIn("No visual tests", result)

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
