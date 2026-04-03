"""Tests for Q244 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

import lidco.cli.commands.q244_cmds as q244_mod


def _make_registry():
    from lidco.cli.commands.registry import CommandRegistry
    reg = CommandRegistry.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    q244_mod.register(reg)
    return reg


def _run(coro):
    return asyncio.run(coro)


class TestReplayCommand(unittest.TestCase):
    def setUp(self):
        reg = _make_registry()
        self.handler = reg._commands["replay"].handler
        # Reset module state
        q244_mod._state.clear()

    def test_no_subcommand_without_load(self):
        result = _run(self.handler(""))
        self.assertIn("No conversation loaded", result)

    def test_no_subcommand_shows_usage(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_load_messages(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        result = _run(self.handler(f"load {msgs}"))
        self.assertIn("Loaded 1", result)

    def test_forward(self):
        msgs = json.dumps([{"role": "user", "content": "hello"}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler("forward"))
        self.assertIn("user", result)
        self.assertIn("hello", result)

    def test_forward_past_end(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        _run(self.handler(f"load {msgs}"))
        _run(self.handler("forward"))
        result = _run(self.handler("forward"))
        self.assertIn("End", result)

    def test_backward_at_start(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler("backward"))
        self.assertIn("beginning", result)

    def test_jump(self):
        msgs = json.dumps([
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "second"},
        ])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler("jump 1"))
        self.assertIn("assistant", result)

    def test_status(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler("status"))
        self.assertIn("-1", result)
        self.assertIn("1", result)

    def test_reset(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        _run(self.handler(f"load {msgs}"))
        _run(self.handler("forward"))
        result = _run(self.handler("reset"))
        self.assertIn("reset", result.lower())

    def test_forward_without_load(self):
        result = _run(self.handler("forward"))
        self.assertIn("No conversation loaded", result)

    def test_load_invalid_json(self):
        result = _run(self.handler("load {bad"))
        self.assertIn("invalid JSON", result)


class TestInspectMessageCommand(unittest.TestCase):
    def setUp(self):
        reg = _make_registry()
        self.handler = reg._commands["inspect-message"].handler

    def test_inspect_basic(self):
        msg = json.dumps({"role": "user", "content": "Hello"})
        result = _run(self.handler(msg))
        self.assertIn("Role: user", result)
        self.assertIn("Content length: 5", result)

    def test_inspect_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_inspect_invalid_json(self):
        result = _run(self.handler("{bad"))
        self.assertIn("invalid JSON", result)

    def test_inspect_with_tool_calls(self):
        msg = json.dumps({"role": "assistant", "content": "x", "tool_calls": [{"id": "1"}]})
        result = _run(self.handler(msg))
        self.assertIn("Tool calls: 1", result)


class TestProfileConversationCommand(unittest.TestCase):
    def setUp(self):
        reg = _make_registry()
        self.handler = reg._commands["profile-conversation"].handler

    def test_profile_basic(self):
        msgs = json.dumps([{"role": "user", "content": "a" * 100}])
        result = _run(self.handler(msgs))
        self.assertIn("Turns: 1", result)

    def test_profile_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_profile_invalid_json(self):
        result = _run(self.handler("{bad"))
        self.assertIn("invalid JSON", result)


class TestAssertCommand(unittest.TestCase):
    def setUp(self):
        reg = _make_registry()
        self.handler = reg._commands["assert"].handler
        q244_mod._state.clear()

    def test_no_subcommand_without_load(self):
        result = _run(self.handler(""))
        self.assertIn("No messages loaded", result)

    def test_no_subcommand_shows_usage(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_load_messages(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        result = _run(self.handler(f"load {msgs}"))
        self.assertIn("Loaded 1", result)

    def test_contains_pass(self):
        msgs = json.dumps([{"role": "user", "content": "hello world"}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler("contains 0 hello"))
        self.assertEqual(result, "PASS")

    def test_contains_fail(self):
        msgs = json.dumps([{"role": "user", "content": "hello world"}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler("contains 0 goodbye"))
        self.assertEqual(result, "FAIL")

    def test_role_pass(self):
        msgs = json.dumps([{"role": "user", "content": "hi"}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler("role 0 user"))
        self.assertEqual(result, "PASS")

    def test_no_empty_with_empty(self):
        msgs = json.dumps([{"role": "user", "content": ""}])
        _run(self.handler(f"load {msgs}"))
        result = _run(self.handler("no-empty"))
        self.assertIn("FAIL", result)

    def test_without_load(self):
        result = _run(self.handler("contains 0 x"))
        self.assertIn("No messages loaded", result)

    def test_run_batch(self):
        msgs = json.dumps([{"role": "user", "content": "hello"}])
        _run(self.handler(f"load {msgs}"))
        assertions = json.dumps([{"type": "contains", "turn": 0, "value": "hello"}])
        result = _run(self.handler(f"run {assertions}"))
        self.assertIn("PASS", result)


if __name__ == "__main__":
    unittest.main()
