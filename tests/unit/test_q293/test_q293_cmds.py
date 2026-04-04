"""Tests for lidco.cli.commands.q293_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q293_cmds import register_q293_commands


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ293Commands(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q293_commands(self.registry)

    def test_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("linear", names)
        self.assertIn("linear-issue", names)
        self.assertIn("linear-cycle", names)
        self.assertIn("linear-dashboard", names)

    # /linear
    def test_linear_teams(self):
        handler = self.registry.commands["linear"].handler
        result = asyncio.run(handler("teams"))
        self.assertIn("Teams", result)
        self.assertIn("ENG", result)

    def test_linear_default_teams(self):
        handler = self.registry.commands["linear"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Teams", result)

    def test_linear_issues_empty(self):
        handler = self.registry.commands["linear"].handler
        result = asyncio.run(handler("issues NoTeam"))
        self.assertIn("No issues", result)

    def test_linear_issue_not_found(self):
        handler = self.registry.commands["linear"].handler
        result = asyncio.run(handler("issue fake-id"))
        self.assertIn("not found", result)

    def test_linear_unknown_subcmd(self):
        handler = self.registry.commands["linear"].handler
        result = asyncio.run(handler("badcmd"))
        self.assertIn("Usage", result)

    # /linear-issue
    def test_linear_issue_auto_status(self):
        handler = self.registry.commands["linear-issue"].handler
        result = asyncio.run(handler("auto-status feature/login"))
        self.assertIn("In Progress", result)

    def test_linear_issue_create_missing_args(self):
        handler = self.registry.commands["linear-issue"].handler
        result = asyncio.run(handler("create"))
        self.assertIn("Usage", result)

    def test_linear_issue_unknown(self):
        handler = self.registry.commands["linear-issue"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    # /linear-cycle
    def test_linear_cycle_create(self):
        handler = self.registry.commands["linear-cycle"].handler
        result = asyncio.run(handler("create Sprint-1"))
        self.assertIn("Created cycle", result)

    def test_linear_cycle_create_missing(self):
        handler = self.registry.commands["linear-cycle"].handler
        result = asyncio.run(handler("create"))
        self.assertIn("Usage", result)

    def test_linear_cycle_unknown(self):
        handler = self.registry.commands["linear-cycle"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    # /linear-dashboard
    def test_dashboard_velocity_empty(self):
        handler = self.registry.commands["linear-dashboard"].handler
        result = asyncio.run(handler("velocity Eng"))
        self.assertIn("No velocity", result)

    def test_dashboard_dist_empty(self):
        handler = self.registry.commands["linear-dashboard"].handler
        result = asyncio.run(handler("dist NoTeam"))
        self.assertIn("No issues", result)

    def test_dashboard_progress_missing(self):
        handler = self.registry.commands["linear-dashboard"].handler
        result = asyncio.run(handler("progress"))
        self.assertIn("Usage", result)

    def test_dashboard_sla_empty(self):
        handler = self.registry.commands["linear-dashboard"].handler
        result = asyncio.run(handler("sla NoTeam"))
        self.assertIn("No open SLA", result)

    def test_dashboard_unknown(self):
        handler = self.registry.commands["linear-dashboard"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
