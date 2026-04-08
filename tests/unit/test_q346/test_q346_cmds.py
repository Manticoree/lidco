"""Tests for lidco.cli.commands.q346_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from lidco.cli.commands.q346_cmds import register_q346_commands


def _make_registry():
    """Return a simple mock registry with a register_slash_command method."""
    registry = MagicMock()
    registry._commands: dict[str, object] = {}

    def _register(name, handler):
        registry._commands[name] = handler

    registry.register_slash_command.side_effect = _register
    return registry


class TestRegisterQ346Commands(unittest.TestCase):
    def test_registers_four_commands(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self.assertEqual(reg.register_slash_command.call_count, 4)

    def test_startup_profile_registered(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self.assertIn("startup-profile", reg._commands)

    def test_shutdown_check_registered(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self.assertIn("shutdown-check", reg._commands)

    def test_health_suite_registered(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self.assertIn("health-suite", reg._commands)

    def test_crash_report_registered(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self.assertIn("crash-report", reg._commands)


class TestStartupProfileHandler(unittest.TestCase):
    def setUp(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self._handler = reg._commands["startup-profile"]

    def test_help_returns_usage(self):
        result = asyncio.run(self._handler("--help"))
        self.assertIn("Usage", result)

    def test_empty_args_returns_usage(self):
        result = asyncio.run(self._handler(""))
        self.assertIn("Usage", result)

    def test_demo_returns_report(self):
        result = asyncio.run(self._handler("demo"))
        self.assertIn("Startup Profiler Report", result)

    def test_custom_modules_returns_results(self):
        result = asyncio.run(self._handler("os sys"))
        self.assertIn("os", result)


class TestShutdownCheckHandler(unittest.TestCase):
    def setUp(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self._handler = reg._commands["shutdown-check"]

    def test_help_returns_usage(self):
        result = asyncio.run(self._handler("--help"))
        self.assertIn("Usage", result)

    def test_demo_returns_shutdown_result(self):
        result = asyncio.run(self._handler("demo"))
        self.assertIn("Shutdown", result)

    def test_unknown_arg_guidance(self):
        result = asyncio.run(self._handler("unknown"))
        self.assertIn("demo", result.lower())


class TestHealthSuiteHandler(unittest.TestCase):
    def setUp(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self._handler = reg._commands["health-suite"]

    def test_help_returns_usage(self):
        result = asyncio.run(self._handler("--help"))
        self.assertIn("Usage", result)

    def test_demo_returns_health_suite(self):
        result = asyncio.run(self._handler("demo"))
        self.assertIn("Health Suite", result)

    def test_empty_returns_health_suite(self):
        result = asyncio.run(self._handler(""))
        self.assertIn("Health Suite", result)


class TestCrashReportHandler(unittest.TestCase):
    def setUp(self):
        reg = _make_registry()
        register_q346_commands(reg)
        self._handler = reg._commands["crash-report"]

    def test_help_returns_usage(self):
        result = asyncio.run(self._handler("--help"))
        self.assertIn("Usage", result)

    def test_empty_returns_usage(self):
        result = asyncio.run(self._handler(""))
        self.assertIn("Usage", result)

    def test_demo_returns_crash_report(self):
        result = asyncio.run(self._handler("demo"))
        self.assertIn("CRASH REPORT", result)

    def test_repro_returns_reproducibility_info(self):
        result = asyncio.run(self._handler("repro"))
        self.assertIn("Python", result)

    def test_unknown_arg_guidance(self):
        result = asyncio.run(self._handler("unknown"))
        self.assertIn("demo", result.lower())


if __name__ == "__main__":
    unittest.main()
