"""Tests for Q240 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class TestQ240Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}
        def _register(cmd):
            self.registered[cmd.name] = cmd
        self.registry.register = _register
        from lidco.cli.commands.q240_cmds import register
        register(self.registry)

    def test_all_commands_registered(self):
        expected = {"stream-stats", "backpressure", "stream-buffer", "flow-control"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_stream_stats(self):
        result = _run(self.registered["stream-stats"].handler(""))
        self.assertIn("tps", result.lower() or "token" in result.lower() or "total" in result.lower())

    def test_backpressure_status(self):
        result = _run(self.registered["backpressure"].handler("status"))
        self.assertIsInstance(result, str)

    def test_backpressure_no_args(self):
        result = _run(self.registered["backpressure"].handler(""))
        self.assertIn("Usage", result)

    def test_stream_buffer_stats(self):
        result = _run(self.registered["stream-buffer"].handler("stats"))
        self.assertIsInstance(result, str)

    def test_stream_buffer_no_args(self):
        result = _run(self.registered["stream-buffer"].handler(""))
        self.assertIn("Usage", result)

    def test_flow_control_status(self):
        result = _run(self.registered["flow-control"].handler("status"))
        self.assertIsInstance(result, str)

    def test_flow_control_no_args(self):
        result = _run(self.registered["flow-control"].handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
