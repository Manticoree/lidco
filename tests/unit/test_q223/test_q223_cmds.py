"""Tests for lidco.cli.commands.q223_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry, SlashCommand
from lidco.cli.commands.q223_cmds import register


def _run(coro):
    return asyncio.run(coro)


class TestQ223Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CommandRegistry()
        register(self.registry)

    def test_all_commands_registered(self) -> None:
        names = {"escalate", "session-perms", "perm-audit", "trust-level"}
        for name in names:
            self.assertIn(name, self.registry._commands, f"/{name} not registered")

    def test_escalate_no_args(self) -> None:
        handler = self.registry._commands["escalate"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_escalate_success(self) -> None:
        handler = self.registry._commands["escalate"].handler
        result = _run(handler("file /a.py need access"))
        self.assertIn("Escalation granted", result)
        self.assertIn("file", result)

    def test_session_perms_list_empty(self) -> None:
        handler = self.registry._commands["session-perms"].handler
        result = _run(handler(""))
        self.assertIn("No session permissions", result)

    def test_session_perms_set(self) -> None:
        handler = self.registry._commands["session-perms"].handler
        result = _run(handler("set file /a.py allow"))
        self.assertIn("Permission set", result)

    def test_perm_audit_summary(self) -> None:
        handler = self.registry._commands["perm-audit"].handler
        result = _run(handler("summary"))
        self.assertIn("PermissionAudit", result)

    def test_trust_level_unknown(self) -> None:
        handler = self.registry._commands["trust-level"].handler
        result = _run(handler("nobody"))
        self.assertIn("0", result)

    def test_trust_level_set(self) -> None:
        handler = self.registry._commands["trust-level"].handler
        result = _run(handler("alice 2"))
        self.assertIn("set to 2", result)
