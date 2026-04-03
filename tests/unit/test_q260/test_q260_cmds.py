"""Tests for lidco.cli.commands.q260_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry
from lidco.cli.commands.q260_cmds import register, _state


class TestQ260Commands(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()
        self.registry = CommandRegistry()
        register(self.registry)

    def _run(self, name: str, args: str = "") -> str:
        cmd = self.registry.get(name)
        self.assertIsNotNone(cmd, f"Command /{name} not registered")
        return asyncio.run(cmd.handler(args))

    def test_classify_data_no_args(self) -> None:
        result = self._run("classify-data")
        self.assertIn("Usage", result)

    def test_classify_data_pii(self) -> None:
        result = self._run("classify-data", "email test@example.com")
        self.assertIn("email", result.lower())

    def test_retention_no_args(self) -> None:
        result = self._run("retention")
        self.assertIn("Usage", result)

    def test_retention_add_list(self) -> None:
        self._run("retention", "add logs .*\\.log 30 delete")
        result = self._run("retention", "list")
        self.assertIn("logs", result)

    def test_retention_hold(self) -> None:
        self._run("retention", "add logs .*\\.log 30 delete")
        result = self._run("retention", "hold logs")
        self.assertIn("Legal hold", result)

    def test_redact_no_args(self) -> None:
        result = self._run("redact")
        self.assertIn("Usage", result)

    def test_redact_pii(self) -> None:
        result = self._run("redact", "email test@example.com")
        self.assertIn("[REDACTED:email]", result)

    def test_compliance_report_all(self) -> None:
        result = self._run("compliance-report", "all")
        self.assertIn("SOC2", result)
        self.assertIn("GDPR", result)


if __name__ == "__main__":
    unittest.main()
