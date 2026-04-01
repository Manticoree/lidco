"""Tests for Q187 CLI commands (Task 1051)."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q187_cmds


def _run(coro):
    return asyncio.run(coro)


class TestSetup(unittest.TestCase):
    def setUp(self):
        q187_cmds._state.clear()


class TestHookifyCommand(TestSetup):
    def _registry(self):
        from lidco.cli.commands.registry import CommandRegistry
        r = CommandRegistry()
        q187_cmds.register(r)
        return r

    def test_register_commands(self):
        r = self._registry()
        self.assertIn("hookify", r._commands)
        self.assertIn("hookify-list", r._commands)
        self.assertIn("hookify-analyze", r._commands)
        self.assertIn("hookify-test", r._commands)

    def test_add_rule(self):
        r = self._registry()
        result = _run(r._commands["hookify"].handler("guard bash rm block Blocked"))
        self.assertIn("guard", result)
        self.assertIn("added", result)

    def test_add_rule_invalid_event(self):
        r = self._registry()
        result = _run(r._commands["hookify"].handler("r INVALID rm block msg"))
        self.assertIn("Invalid event_type", result)

    def test_add_rule_invalid_action(self):
        r = self._registry()
        result = _run(r._commands["hookify"].handler("r bash rm INVALID msg"))
        self.assertIn("Invalid action", result)

    def test_add_rule_missing_args(self):
        r = self._registry()
        result = _run(r._commands["hookify"].handler(""))
        self.assertIn("Usage", result)


class TestHookifyListCommand(TestSetup):
    def _registry(self):
        from lidco.cli.commands.registry import CommandRegistry
        r = CommandRegistry()
        q187_cmds.register(r)
        return r

    def test_empty_list(self):
        r = self._registry()
        result = _run(r._commands["hookify-list"].handler(""))
        self.assertIn("No hookify rules", result)

    def test_list_after_add(self):
        r = self._registry()
        _run(r._commands["hookify"].handler("guard bash rm block Blocked"))
        result = _run(r._commands["hookify-list"].handler(""))
        self.assertIn("guard", result)
        self.assertIn("block", result)


class TestHookifyAnalyzeCommand(TestSetup):
    def _registry(self):
        from lidco.cli.commands.registry import CommandRegistry
        r = CommandRegistry()
        q187_cmds.register(r)
        return r

    def test_no_history(self):
        r = self._registry()
        result = _run(r._commands["hookify-analyze"].handler(""))
        self.assertIn("No conversation history", result)

    def test_with_history(self):
        r = self._registry()
        q187_cmds._state["conversation_history"] = [
            {"role": "user", "content": "run rm -rf /tmp"},
        ]
        result = _run(r._commands["hookify-analyze"].handler(""))
        self.assertIn("Suggested rules", result)

    def test_no_suggestions(self):
        r = self._registry()
        q187_cmds._state["conversation_history"] = [
            {"role": "user", "content": "hello world"},
        ]
        result = _run(r._commands["hookify-analyze"].handler(""))
        self.assertIn("No rule suggestions", result)


class TestHookifyTestCommand(TestSetup):
    def _registry(self):
        from lidco.cli.commands.registry import CommandRegistry
        r = CommandRegistry()
        q187_cmds.register(r)
        return r

    def test_no_engine(self):
        r = self._registry()
        result = _run(r._commands["hookify-test"].handler("bash rm -rf"))
        self.assertIn("No hookify rules", result)

    def test_match(self):
        r = self._registry()
        _run(r._commands["hookify"].handler("guard bash rm block Blocked"))
        result = _run(r._commands["hookify-test"].handler("bash rm something"))
        self.assertIn("guard", result)
        self.assertIn("matched", result)

    def test_no_match(self):
        r = self._registry()
        _run(r._commands["hookify"].handler("guard bash rm block Blocked"))
        result = _run(r._commands["hookify-test"].handler("bash ls -la"))
        self.assertIn("No rules matched", result)

    def test_missing_args(self):
        r = self._registry()
        result = _run(r._commands["hookify-test"].handler(""))
        self.assertIn("Usage", result)

    def test_invalid_event_type(self):
        r = self._registry()
        result = _run(r._commands["hookify-test"].handler("INVALID content"))
        self.assertIn("Invalid event_type", result)


if __name__ == "__main__":
    unittest.main()
