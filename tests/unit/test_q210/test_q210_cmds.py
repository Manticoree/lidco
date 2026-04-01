"""Tests for lidco.cli.commands.q210_cmds."""

from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q210_cmds


class _FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register(self, cmd: object) -> None:
        self.commands[cmd.name] = cmd  # type: ignore[attr-defined]


class TestQ210Cmds(unittest.TestCase):
    def setUp(self) -> None:
        q210_cmds._state.clear()
        self.registry = _FakeRegistry()
        q210_cmds.register(self.registry)

    def test_commands_registered(self) -> None:
        assert "pair" in self.registry.commands
        assert "explain-code" in self.registry.commands
        assert "suggest" in self.registry.commands
        assert "complete" in self.registry.commands

    def test_pair_init_and_state(self) -> None:
        handler = self.registry.commands["pair"].handler
        result = asyncio.run(handler("init hello"))
        assert "initialized" in result.lower()
        result = asyncio.run(handler("state"))
        assert "hello" in result

    def test_explain_code_brief(self) -> None:
        handler = self.registry.commands["explain-code"].handler
        result = asyncio.run(handler("brief x = 1"))
        assert "brief" in result.lower()

    def test_suggest_usage(self) -> None:
        handler = self.registry.commands["suggest"].handler
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_complete_prefix(self) -> None:
        handler = self.registry.commands["complete"].handler
        result = asyncio.run(handler("prefix pri"))
        assert "print" in result.lower()


if __name__ == "__main__":
    unittest.main()
