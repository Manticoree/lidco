"""Tests for Q211 CLI commands."""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    def __init__(self):
        self.cmds: dict = {}

    def register(self, cmd):
        self.cmds[cmd.name] = cmd


class TestCommandRegistration(unittest.TestCase):
    def test_all_commands_registered(self):
        from lidco.cli.commands.q211_cmds import register

        reg = _FakeRegistry()
        register(reg)
        self.assertIn("health-score", reg.cmds)
        self.assertIn("tech-debt", reg.cmds)
        self.assertIn("complexity", reg.cmds)
        self.assertIn("churn", reg.cmds)


class TestHealthScoreCommand(unittest.TestCase):
    def test_returns_score(self):
        from lidco.cli.commands.q211_cmds import register

        reg = _FakeRegistry()
        register(reg)
        result = _run(reg.cmds["health-score"].handler(""))
        self.assertIn("Health score", result)
        self.assertIn("grade", result)


class TestTechDebtCommand(unittest.TestCase):
    def test_scan_file(self):
        from lidco.cli.commands.q211_cmds import register

        reg = _FakeRegistry()
        register(reg)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write("# TODO: fix me\npass\n")
            path = f.name
        try:
            result = _run(reg.cmds["tech-debt"].handler(path))
            self.assertIn("Debt items: 1", result)
        finally:
            os.unlink(path)


class TestComplexityCommand(unittest.TestCase):
    def test_analyze_file(self):
        from lidco.cli.commands.q211_cmds import register

        reg = _FakeRegistry()
        register(reg)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write("def foo():\n    return 1\n")
            path = f.name
        try:
            result = _run(reg.cmds["complexity"].handler(path))
            self.assertIn("Functions: 1", result)
        finally:
            os.unlink(path)


class TestChurnCommand(unittest.TestCase):
    def test_empty_summary(self):
        from lidco.cli.commands.q211_cmds import register

        reg = _FakeRegistry()
        register(reg)
        result = _run(reg.cmds["churn"].handler(""))
        self.assertIn("No churn data", result)
