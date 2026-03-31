"""Tests for Q152 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q152_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ152Commands(unittest.TestCase):
    def setUp(self):
        q152_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q152_cmds.register(MockRegistry())
        self.handler = self.registered["error"].handler

    def test_command_registered(self):
        self.assertIn("error", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- report ---

    def test_report_no_args(self):
        result = _run(self.handler("report"))
        self.assertIn("Usage", result)

    def test_report_basic(self):
        result = _run(self.handler("report Connection refused"))
        self.assertIn("Error Report", result)

    def test_report_contains_type(self):
        result = _run(self.handler("report Something broke"))
        self.assertIn("RuntimeError", result)

    def test_report_contains_message(self):
        result = _run(self.handler("report file not found"))
        self.assertIn("file not found", result)

    # --- categorize ---

    def test_categorize_no_args(self):
        result = _run(self.handler("categorize"))
        self.assertIn("Usage", result)

    def test_categorize_match(self):
        result = _run(self.handler("categorize Connection refused"))
        self.assertIn("Category", result)

    def test_categorize_no_match(self):
        result = _run(self.handler("categorize something random unique xyz"))
        self.assertIn("No matching", result)

    def test_categorize_shows_severity(self):
        result = _run(self.handler("categorize timed out"))
        self.assertIn("critical", result)

    # --- suggest ---

    def test_suggest_no_args(self):
        result = _run(self.handler("suggest"))
        self.assertIn("Usage", result)

    def test_suggest_with_match(self):
        result = _run(self.handler("suggest No module named foo"))
        self.assertIn("Install", result)

    def test_suggest_no_match(self):
        result = _run(self.handler("suggest asdf qwerty unique 12345"))
        self.assertIn("No solutions", result)

    def test_suggest_numbered(self):
        result = _run(self.handler("suggest Permission denied"))
        self.assertIn("1.", result)

    # --- friendly ---

    def test_friendly_no_args(self):
        result = _run(self.handler("friendly"))
        self.assertIn("Usage", result)

    def test_friendly_translated(self):
        result = _run(self.handler("friendly something happened"))
        self.assertIn("Error:", result)

    def test_friendly_contains_technical(self):
        result = _run(self.handler("friendly test message"))
        self.assertIn("Technical:", result)


if __name__ == "__main__":
    unittest.main()
