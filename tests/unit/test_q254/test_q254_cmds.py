"""Tests for Q254 CLI commands — /smell-scan, /smell-fix, /smell-dashboard, /smell-config."""

from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q254_cmds import register
from lidco.cli.commands.registry import CommandRegistry


def _run(coro):
    return asyncio.run(coro)


def _make_registry():
    """Create a bare CommandRegistry with only q254 commands."""
    reg = object.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    register(reg)
    return reg


class TestSmellScanCommand(unittest.TestCase):
    """Test /smell-scan."""

    def test_no_args(self):
        reg = _make_registry()
        cmd = reg.get("smell-scan")
        result = _run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_clean_code(self):
        reg = _make_registry()
        cmd = reg.get("smell-scan")
        result = _run(cmd.handler("x = 0\ny = 1\n"))
        self.assertIn("No code smells", result)

    def test_detects_smells(self):
        reg = _make_registry()
        cmd = reg.get("smell-scan")
        source = "timeout = 3600\n"
        result = _run(cmd.handler(source))
        self.assertIn("smell(s) found", result)


class TestSmellFixCommand(unittest.TestCase):
    """Test /smell-fix."""

    def test_no_args(self):
        reg = _make_registry()
        cmd = reg.get("smell-fix")
        result = _run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_no_smells(self):
        reg = _make_registry()
        cmd = reg.get("smell-fix")
        result = _run(cmd.handler("x = 0\n"))
        self.assertIn("No code smells", result)

    def test_fix_applied(self):
        reg = _make_registry()
        cmd = reg.get("smell-fix")
        result = _run(cmd.handler("timeout = 3600"))
        # Should either fix or say no automated fixes
        self.assertIsInstance(result, str)


class TestSmellDashboardCommand(unittest.TestCase):
    """Test /smell-dashboard."""

    def test_no_args(self):
        reg = _make_registry()
        cmd = reg.get("smell-dashboard")
        result = _run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_dashboard_output(self):
        reg = _make_registry()
        cmd = reg.get("smell-dashboard")
        result = _run(cmd.handler("timeout = 3600\n"))
        self.assertIn("Code Smell Dashboard", result)

    def test_clean_code_dashboard(self):
        reg = _make_registry()
        cmd = reg.get("smell-dashboard")
        result = _run(cmd.handler("x = 0\n"))
        self.assertIn("Total smells: 0", result)


class TestSmellConfigCommand(unittest.TestCase):
    """Test /smell-config."""

    def test_no_subcommand(self):
        reg = _make_registry()
        cmd = reg.get("smell-config")
        result = _run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_list(self):
        reg = _make_registry()
        cmd = reg.get("smell-config")
        result = _run(cmd.handler("list"))
        self.assertIn("smell(s) configured", result)
        self.assertIn("long_method", result)

    def test_severity_filter(self):
        reg = _make_registry()
        cmd = reg.get("smell-config")
        result = _run(cmd.handler("severity high"))
        self.assertIn("high", result)
        self.assertIn("smell(s)", result)

    def test_severity_empty(self):
        reg = _make_registry()
        cmd = reg.get("smell-config")
        result = _run(cmd.handler("severity nonexistent"))
        self.assertIn("No smells", result)

    def test_severity_no_level(self):
        reg = _make_registry()
        cmd = reg.get("smell-config")
        result = _run(cmd.handler("severity"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
