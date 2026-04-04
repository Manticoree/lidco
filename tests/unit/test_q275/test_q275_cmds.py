"""Tests for lidco.cli.commands.q275_cmds."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class TestQ275Commands(unittest.TestCase):
    def setUp(self):
        # Reset module-level state between tests
        import lidco.cli.commands.q275_cmds as mod
        mod._state.clear()

        self.registry = MagicMock()
        self.handlers: dict[str, object] = {}

        def fake_register(cmd):
            self.handlers[cmd.name] = cmd.handler

        self.registry.register.side_effect = fake_register
        mod.register(self.registry)

    def test_classify_error_syntax(self):
        handler = self.handlers["classify-error"]
        result = _run(handler("SyntaxError: invalid syntax"))
        data = json.loads(result)
        self.assertEqual(data["type"], "syntax")

    def test_classify_error_empty(self):
        handler = self.handlers["classify-error"]
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_recovery_summary(self):
        handler = self.handlers["recovery"]
        result = _run(handler(""))
        data = json.loads(result)
        self.assertIn("chain_count", data)

    def test_recovery_chain(self):
        handler = self.handlers["recovery"]
        result = _run(handler("chain network"))
        data = json.loads(result)
        self.assertEqual(data["error_type"], "network")

    def test_recovery_next(self):
        handler = self.handlers["recovery"]
        result = _run(handler("next network 0"))
        data = json.loads(result)
        self.assertIn("type", data)

    def test_self_heal(self):
        handler = self.handlers["self-heal"]
        result = _run(handler("ModuleNotFoundError: No module named 'os' | x = os.path"))
        data = json.loads(result)
        self.assertTrue(data["success"])

    def test_self_heal_empty(self):
        handler = self.handlers["self-heal"]
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_error_patterns_summary(self):
        handler = self.handlers["error-patterns"]
        result = _run(handler(""))
        data = json.loads(result)
        self.assertIn("resolution_count", data)

    def test_error_patterns_record_and_suggest(self):
        handler = self.handlers["error-patterns"]
        _run(handler("record KeyError | check key | true"))
        result = _run(handler("suggest KeyError"))
        data = json.loads(result)
        self.assertEqual(len(data), 1)

    def test_error_patterns_top(self):
        handler = self.handlers["error-patterns"]
        _run(handler("record Err | fix | true"))
        result = _run(handler("top"))
        data = json.loads(result)
        self.assertEqual(len(data), 1)


if __name__ == "__main__":
    unittest.main()
