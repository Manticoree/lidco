"""Tests for CLI commands in q236_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q236_cmds import register
from lidco.cli.commands.registry import SlashCommand


def _make_registry():
    """Create a minimal registry and register Q236 commands."""

    class MiniRegistry:
        def __init__(self) -> None:
            self._commands: dict[str, SlashCommand] = {}

        def register(self, cmd: SlashCommand) -> None:
            self._commands[cmd.name] = cmd

        def get(self, name: str) -> SlashCommand | None:
            return self._commands.get(name)

    reg = MiniRegistry()
    register(reg)
    return reg


class TestQ236Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = _make_registry()

    def test_teleport_export_registered(self) -> None:
        self.assertIsNotNone(self.reg.get("teleport-export"))

    def test_teleport_export_default(self) -> None:
        cmd = self.reg.get("teleport-export")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Exported session", result)

    def test_teleport_export_with_args(self) -> None:
        cmd = self.reg.get("teleport-export")
        result = asyncio.run(cmd.handler("mysession hello world"))
        self.assertIn("mysession", result)
        self.assertIn("1 messages", result)

    def test_teleport_import_registered(self) -> None:
        self.assertIsNotNone(self.reg.get("teleport-import"))

    def test_teleport_import_no_args(self) -> None:
        cmd = self.reg.get("teleport-import")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_teleport_import_bad_json(self) -> None:
        cmd = self.reg.get("teleport-import")
        result = asyncio.run(cmd.handler("{bad"))
        self.assertIn("Invalid JSON", result)

    def test_share_registered(self) -> None:
        self.assertIsNotNone(self.reg.get("share"))

    def test_share_creates_link(self) -> None:
        cmd = self.reg.get("share")
        result = asyncio.run(cmd.handler("mysession some content"))
        self.assertIn("Share created", result)
        self.assertIn("mysession", result)

    def test_share_list_no_shares(self) -> None:
        cmd = self.reg.get("share-list")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("No shares", result)
