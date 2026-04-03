"""Tests for Q239 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class TestQ239Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}
        def _register(cmd):
            self.registered[cmd.name] = cmd
        self.registry.register = _register
        from lidco.cli.commands.q239_cmds import register
        register(self.registry)

    def test_all_commands_registered(self):
        expected = {"validate-messages", "normalize", "schema-info", "message-stats"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_validate_messages_valid(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        result = _run(self.registered["validate-messages"].handler(msgs))
        self.assertIn("PASS", result)

    def test_validate_messages_invalid(self):
        msgs = json.dumps([{"role": "bad"}])
        result = _run(self.registered["validate-messages"].handler(msgs))
        self.assertIn("FAIL", result)

    def test_validate_messages_no_args(self):
        result = _run(self.registered["validate-messages"].handler(""))
        self.assertIn("Usage", result)

    def test_validate_messages_bad_json(self):
        result = _run(self.registered["validate-messages"].handler("{bad"))
        self.assertIn("Invalid JSON", result)

    def test_normalize(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        result = _run(self.registered["normalize"].handler(msgs))
        parsed = json.loads(result)
        self.assertEqual(parsed[0]["role"], "user")

    def test_normalize_no_args(self):
        result = _run(self.registered["normalize"].handler(""))
        self.assertIn("Usage", result)

    def test_schema_info_list(self):
        result = _run(self.registered["schema-info"].handler(""))
        self.assertIn("openai", result)
        self.assertIn("anthropic", result)

    def test_schema_info_provider(self):
        result = _run(self.registered["schema-info"].handler("openai"))
        parsed = json.loads(result)
        self.assertIn("roles", parsed)

    def test_schema_info_unknown(self):
        result = _run(self.registered["schema-info"].handler("unknown"))
        self.assertIn("No schema", result)

    def test_message_stats(self):
        msgs = json.dumps([
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ])
        result = _run(self.registered["message-stats"].handler(msgs))
        self.assertIn("Message count: 2", result)
        self.assertIn("user: 1", result)

    def test_message_stats_no_args(self):
        result = _run(self.registered["message-stats"].handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
