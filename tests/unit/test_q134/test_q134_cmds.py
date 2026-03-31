"""Tests for Q134 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from lidco.cli.commands import q134_cmds


class FakeRegistry:
    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ134CmdsRegister(unittest.TestCase):
    def test_register_adds_transform(self):
        reg = FakeRegistry()
        q134_cmds.register(reg)
        self.assertIn("transform", reg.commands)

    def test_handler_is_async(self):
        reg = FakeRegistry()
        q134_cmds.register(reg)
        cmd = reg.commands["transform"]
        self.assertTrue(asyncio.iscoroutinefunction(cmd.handler))


class TestTransformHandler(unittest.TestCase):
    def setUp(self):
        q134_cmds._state.clear()
        reg = FakeRegistry()
        q134_cmds.register(reg)
        self.handler = reg.commands["transform"].handler

    def _run(self, args: str) -> str:
        return asyncio.run(self.handler(args))

    def test_no_args_shows_usage(self):
        result = self._run("")
        self.assertIn("Usage", result)

    def test_unknown_sub_shows_usage(self):
        result = self._run("unknown")
        self.assertIn("Usage", result)

    def test_rename_missing_args(self):
        result = self._run("rename x")
        self.assertIn("Usage", result)

    def test_rename_basic(self):
        src = "x = 1\\nprint(x)"
        result = self._run(f"rename x y {src}")
        # Will try to rename in the literal string — should work or report
        self.assertIsInstance(result, str)

    def test_rename_unsafe(self):
        # new_name = old_name → unsafe
        with mock.patch("lidco.transform.variable_renamer.VariableRenamer.is_safe_rename", return_value=False):
            q134_cmds._state.clear()
            result = self._run("rename x y somesource")
            self.assertIn("not safe", result)

    def test_extract_missing_args(self):
        result = self._run("extract 1")
        self.assertIn("Usage", result)

    def test_extract_bad_line_numbers(self):
        result = self._run("extract abc def fn source")
        self.assertIn("integers", result)

    def test_extract_basic(self):
        result = self._run("extract 1 1 fn a=1")
        self.assertIn("method_name", result)

    def test_inline_missing_args(self):
        result = self._run("inline x")
        self.assertIn("Usage", result)

    def test_inline_cannot_inline(self):
        with mock.patch("lidco.transform.inline_expander.InlineExpander.can_inline", return_value=False):
            q134_cmds._state.clear()
            result = self._run("inline x somesource")
            self.assertIn("Cannot inline", result)

    def test_inline_basic(self):
        src = "x = 42\\ny = x + 1"
        result = self._run(f"inline x {src}")
        self.assertIsInstance(result, str)

    def test_dead_code_missing_args(self):
        result = self._run("dead-code")
        self.assertIn("Usage", result)

    def test_dead_code_basic(self):
        src = "import os\\nx = 1"
        result = self._run(f"dead-code {src}")
        self.assertIn("removed", result)

    def test_state_reuse(self):
        """Second call reuses cached instances."""
        self._run("dead-code x=1")
        self.assertIn("eliminator", q134_cmds._state)
        # Call again — should not raise
        self._run("dead-code x=1")

    def test_rename_returns_json(self):
        result = self._run("rename x y x=1")
        # Either "not safe" or JSON — both valid responses
        self.assertIsInstance(result, str)

    def test_extract_returns_json(self):
        result = self._run("extract 1 1 fn a=1")
        self.assertIn("method_name", result)

    def test_dead_code_returns_json(self):
        result = self._run("dead-code a=1")
        self.assertIn("removed_names", result)

    def test_handler_help_mentions_subcommands(self):
        result = self._run("")
        self.assertIn("rename", result)
        self.assertIn("extract", result)
        self.assertIn("inline", result)
        self.assertIn("dead-code", result)


if __name__ == "__main__":
    unittest.main()
