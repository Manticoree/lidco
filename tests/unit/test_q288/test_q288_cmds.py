"""Tests for lidco.cli.commands.q288_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q288_cmds import register_q288_commands


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ288Commands(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q288_commands(self.registry)

    def test_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("verify-logic", names)
        self.assertIn("verify-code", names)
        self.assertIn("link-evidence", names)
        self.assertIn("verification-report", names)

    # -- /verify-logic ----------------------------------------------------

    def test_verify_logic_empty(self):
        handler = self.registry.commands["verify-logic"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_verify_logic_single_stmt(self):
        handler = self.registry.commands["verify-logic"].handler
        result = asyncio.run(handler("only one"))
        self.assertIn("at least two", result.lower())

    def test_verify_logic_valid(self):
        handler = self.registry.commands["verify-logic"].handler
        result = asyncio.run(handler("server crash detected | crash caused downtime"))
        self.assertIn("Valid: True", result)

    def test_verify_logic_issues(self):
        handler = self.registry.commands["verify-logic"].handler
        result = asyncio.run(handler("apples grow nicely | quantum physics rules"))
        self.assertIn("Gap", result)

    # -- /verify-code -----------------------------------------------------

    def test_verify_code_empty(self):
        handler = self.registry.commands["verify-code"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_verify_code_no_separator(self):
        handler = self.registry.commands["verify-code"].handler
        result = asyncio.run(handler("just code"))
        self.assertIn("separated by", result.lower())

    def test_verify_code_valid(self):
        handler = self.registry.commands["verify-code"].handler
        result = asyncio.run(handler("x = 1 | x = 2"))
        self.assertIn("Valid: True", result)

    # -- /link-evidence ---------------------------------------------------

    def test_link_evidence_empty(self):
        handler = self.registry.commands["link-evidence"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_link_evidence_found(self):
        handler = self.registry.commands["link-evidence"].handler
        result = asyncio.run(handler("server crashed | logs:server crashed at noon"))
        self.assertIn("Source: logs", result)

    # -- /verification-report ---------------------------------------------

    def test_report_generate_empty(self):
        handler = self.registry.commands["verification-report"].handler
        result = asyncio.run(handler("generate"))
        self.assertIn("Score: 0.0", result)

    def test_report_add_and_generate(self):
        handler = self.registry.commands["verification-report"].handler
        asyncio.run(handler("add logic problem_found"))
        result = asyncio.run(handler("generate"))
        self.assertIn("logic", result)

    def test_report_reset(self):
        handler = self.registry.commands["verification-report"].handler
        asyncio.run(handler("add section1"))
        result = asyncio.run(handler("reset"))
        self.assertIn("reset", result.lower())


if __name__ == "__main__":
    unittest.main()
