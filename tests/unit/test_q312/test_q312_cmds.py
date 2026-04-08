"""Tests for Q312 Task 1676 — CLI commands."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q312_cmds import register_q312_commands


class _FakeRegistry:
    """Minimal registry stub that captures registrations."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler) -> None:
        self.commands[name] = (desc, handler)


class TestRegisterQ312Commands(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q312_commands(self.reg)

    def test_all_commands_registered(self):
        expected = {"load-profile", "load-run", "load-report", "load-bottleneck"}
        self.assertEqual(set(self.reg.commands.keys()), expected)


class TestLoadProfileHandler(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q312_commands(self.reg)
        _, self.handler = self.reg.commands["load-profile"]

    def test_default(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Profile", result)
        self.assertIn("steady", result)

    def test_with_type_ramp(self):
        result = asyncio.run(self.handler("--type ramp_up --users 50 mytest"))
        self.assertIn("ramp_up", result)
        self.assertIn("mytest", result)

    def test_with_type_spike(self):
        result = asyncio.run(self.handler("--type spike --spike-users 100"))
        self.assertIn("spike", result)

    def test_with_type_soak(self):
        result = asyncio.run(self.handler("--type soak --duration 3600"))
        self.assertIn("soak", result)

    def test_custom_users(self):
        result = asyncio.run(self.handler("--users 42"))
        self.assertIn("42", result)


class TestLoadRunHandler(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q312_commands(self.reg)
        _, self.handler = self.reg.commands["load-run"]

    def test_default(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Load test complete", result)
        self.assertIn("Requests", result)
        self.assertIn("Latency", result)

    def test_with_args(self):
        result = asyncio.run(self.handler("--users 2 --duration 1"))
        self.assertIn("Load test complete", result)


class TestLoadReportHandler(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q312_commands(self.reg)
        _, self.handler = self.reg.commands["load-report"]

    def test_default(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Load Test Report", result)
        self.assertIn("Latency", result)
        self.assertIn("Throughput", result)

    def test_with_threshold(self):
        result = asyncio.run(self.handler("--threshold-ms 1 --duration 1"))
        self.assertIn("Load Test Report", result)


class TestLoadBottleneckHandler(unittest.TestCase):
    def setUp(self):
        self.reg = _FakeRegistry()
        register_q312_commands(self.reg)
        _, self.handler = self.reg.commands["load-bottleneck"]

    def test_default(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Bottleneck analysis", result)

    def test_with_args(self):
        result = asyncio.run(self.handler("--users 2 --duration 1 --slow-ms 1"))
        self.assertIn("Bottleneck analysis", result)


if __name__ == "__main__":
    unittest.main()
