"""Tests for Q248 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q248_cmds import register
from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def _make_registry(messages=None):
    """Create a CommandRegistry with a mock session carrying *messages*."""
    reg = CommandRegistry()
    session = MagicMock()
    session.messages = messages or []
    reg._session = session
    register(reg)
    return reg


def _run(handler, args=""):
    return asyncio.run(handler(args))


class TestTurnAnalysisCmd(unittest.TestCase):
    def test_summary(self):
        reg = _make_registry([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ])
        result = _run(reg._commands["turn-analysis"].handler, "summary")
        self.assertIn("Turns: 2", result)

    def test_deltas(self):
        reg = _make_registry([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there, how are you?"},
        ])
        result = _run(reg._commands["turn-analysis"].handler, "deltas")
        self.assertIn("Token deltas:", result)

    def test_specific_index(self):
        reg = _make_registry([{"role": "user", "content": "Hello"}])
        result = _run(reg._commands["turn-analysis"].handler, "0")
        self.assertIn("Turn 0", result)

    def test_index_out_of_range(self):
        reg = _make_registry([{"role": "user", "content": "Hello"}])
        result = _run(reg._commands["turn-analysis"].handler, "5")
        self.assertIn("out of range", result)

    def test_usage(self):
        reg = _make_registry()
        result = _run(reg._commands["turn-analysis"].handler, "")
        self.assertIn("Usage:", result)


class TestPatternsCmd(unittest.TestCase):
    def test_loops(self):
        msgs = [
            {"role": "user", "content": "fix it"},
            {"role": "assistant", "content": "done"},
            {"role": "user", "content": "fix it"},
        ]
        reg = _make_registry(msgs)
        result = _run(reg._commands["patterns"].handler, "loops")
        self.assertIn("loop", result.lower())

    def test_dead_ends(self):
        msgs = [
            {"role": "user", "content": "do it"},
            {"role": "assistant", "content": ""},
        ]
        reg = _make_registry(msgs)
        result = _run(reg._commands["patterns"].handler, "dead-ends")
        self.assertIn("0", result)

    def test_retries(self):
        msgs = [
            {"role": "assistant", "content": "x", "tool_calls": ["read"]},
        ] * 5
        reg = _make_registry(msgs)
        result = _run(reg._commands["patterns"].handler, "retries")
        self.assertIn("read", result)

    def test_all(self):
        reg = _make_registry([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
        result = _run(reg._commands["patterns"].handler, "all")
        self.assertIn("No problematic patterns", result)

    def test_usage(self):
        reg = _make_registry()
        result = _run(reg._commands["patterns"].handler, "unknown")
        self.assertIn("Usage:", result)


class TestPredictSuccessCmd(unittest.TestCase):
    def test_predict(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        reg = _make_registry(msgs)
        result = _run(reg._commands["predict-success"].handler, "")
        self.assertIn("Likelihood:", result)
        self.assertIn("Recommendation:", result)

    def test_health(self):
        msgs = [{"role": "user", "content": "hi"}]
        reg = _make_registry(msgs)
        result = _run(reg._commands["predict-success"].handler, "health")
        self.assertIn("Length:", result)
        self.assertIn("Score:", result)


class TestExportConversationCmd(unittest.TestCase):
    def test_markdown(self):
        msgs = [{"role": "user", "content": "Hello"}]
        reg = _make_registry(msgs)
        result = _run(reg._commands["export-conversation"].handler, "markdown")
        self.assertIn("# Conversation Export", result)

    def test_json(self):
        msgs = [{"role": "user", "content": "Hello"}]
        reg = _make_registry(msgs)
        result = _run(reg._commands["export-conversation"].handler, "json")
        self.assertIn('"messages"', result)

    def test_html(self):
        msgs = [{"role": "user", "content": "Hello"}]
        reg = _make_registry(msgs)
        result = _run(reg._commands["export-conversation"].handler, "html")
        self.assertIn("<html>", result)

    def test_default_format(self):
        msgs = [{"role": "user", "content": "Hello"}]
        reg = _make_registry(msgs)
        result = _run(reg._commands["export-conversation"].handler, "")
        self.assertIn("# Conversation Export", result)

    def test_unsupported_format(self):
        reg = _make_registry([{"role": "user", "content": "hi"}])
        result = _run(reg._commands["export-conversation"].handler, "csv")
        self.assertIn("Unsupported format", result)


class TestRegistration(unittest.TestCase):
    def test_all_commands_registered(self):
        reg = _make_registry()
        for name in ("turn-analysis", "patterns", "predict-success", "export-conversation"):
            self.assertIn(name, reg._commands, f"/{name} not registered")
            self.assertIsInstance(reg._commands[name], SlashCommand)


if __name__ == "__main__":
    unittest.main()
