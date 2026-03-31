"""Tests for Q140 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands import q140_cmds


class TestQ140Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        q140_cmds._state.clear()
        q140_cmds.register(self.registry)
        self.handler = self.registry.register.call_args[0][0].handler

    def _run(self, args: str) -> str:
        return asyncio.run(self.handler(args))

    def test_register_called(self):
        self.registry.register.assert_called_once()
        cmd = self.registry.register.call_args[0][0]
        self.assertEqual(cmd.name, "input")

    def test_usage(self):
        result = self._run("")
        self.assertIn("Usage:", result)
        self.assertIn("parse", result)
        self.assertIn("suggest", result)
        self.assertIn("help", result)
        self.assertIn("sanitize", result)

    def test_parse_basic(self):
        result = self._run("parse cmd hello world")
        data = json.loads(result)
        self.assertIn("hello", data["positional"])
        self.assertIn("world", data["positional"])

    def test_parse_no_args(self):
        result = self._run("parse mycmd")
        data = json.loads(result)
        self.assertEqual(data["positional"], [])

    def test_parse_default_cmd_name(self):
        result = self._run("parse")
        data = json.loads(result)
        self.assertIsInstance(data["positional"], list)

    def test_suggest_no_args(self):
        result = self._run("suggest")
        self.assertIn("Usage:", result)

    def test_suggest_unknown(self):
        result = self._run("suggest zzzzz")
        self.assertIn("Unknown command", result)

    def test_suggest_with_registry_commands(self):
        self.registry._commands = {"commit": None, "config": None, "help": None}
        result = self._run("suggest comit")
        self.assertIn("Did you mean", result)

    def test_help_empty(self):
        result = self._run("help")
        self.assertIn("No commands found", result)

    def test_help_specific(self):
        result = self._run("help nonexistent")
        self.assertIn("Unknown command", result)

    def test_sanitize_no_args(self):
        result = self._run("sanitize")
        self.assertIn("Usage:", result)

    def test_sanitize_clean(self):
        result = self._run("sanitize hello world")
        data = json.loads(result)
        self.assertEqual(data["sanitized"], "hello world")
        self.assertFalse(data["was_modified"])

    def test_sanitize_suspicious(self):
        result = self._run("sanitize hello; rm -rf")
        data = json.loads(result)
        self.assertTrue(len(data["warnings"]) > 0)

    def test_unknown_sub(self):
        result = self._run("unknown")
        self.assertIn("Usage:", result)

    def test_state_persistence(self):
        self._run("sanitize abc")
        self.assertIn("sanitizer", q140_cmds._state)

    def test_parse_flags(self):
        result = self._run("parse cmd --verbose")
        data = json.loads(result)
        self.assertIn("--verbose", data["positional"])

    def test_sanitize_original_preserved(self):
        result = self._run("sanitize test input")
        data = json.loads(result)
        self.assertEqual(data["original"], "test input")

    def test_suggest_format(self):
        self.registry._commands = {"status": None}
        result = self._run("suggest statu")
        # Should contain suggestion or unknown
        self.assertIsInstance(result, str)

    def test_help_returns_string(self):
        result = self._run("help")
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
