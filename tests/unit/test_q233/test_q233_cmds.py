"""Tests for lidco.cli.commands.q233_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands import q233_cmds


class _FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register(self, cmd: object) -> None:
        self.commands[cmd.name] = cmd  # type: ignore[attr-defined]


class TestQ233Cmds(unittest.TestCase):
    def setUp(self) -> None:
        # Clear cached state on handlers
        for attr in ("_mgr", "_gen"):
            for fn_name in ("turn_budget_handler", "budget_checkpoint_handler", "session_report_handler"):
                # handlers are closures, so we re-register each time
                pass
        self.registry = _FakeRegistry()
        q233_cmds.register(self.registry)

    def test_commands_registered(self) -> None:
        assert "session-budget" in self.registry.commands
        assert "turn-budget" in self.registry.commands
        assert "budget-checkpoint" in self.registry.commands
        assert "session-report" in self.registry.commands

    def test_session_budget_init(self) -> None:
        handler = self.registry.commands["session-budget"].handler
        result = asyncio.run(handler("init claude-3 200000"))
        assert "claude-3" in result
        assert "200,000" in result

    def test_session_budget_estimate(self) -> None:
        handler = self.registry.commands["session-budget"].handler
        result = asyncio.run(handler("estimate hello world"))
        assert "Estimated" in result

    def test_session_budget_recommend(self) -> None:
        handler = self.registry.commands["session-budget"].handler
        result = asyncio.run(handler("recommend 128000"))
        assert "system" in result

    def test_session_budget_usage(self) -> None:
        handler = self.registry.commands["session-budget"].handler
        result = asyncio.run(handler("unknown"))
        assert "Usage" in result

    def test_turn_budget_begin_end(self) -> None:
        handler = self.registry.commands["turn-budget"].handler
        result = asyncio.run(handler("begin 1000"))
        assert "Turn 1" in result
        result = asyncio.run(handler("end 1500"))
        assert "500" in result

    def test_budget_checkpoint_save_load(self) -> None:
        handler = self.registry.commands["budget-checkpoint"].handler
        result = asyncio.run(handler("save mysess 5000"))
        assert "mysess" in result
        result = asyncio.run(handler("load mysess"))
        assert "5,000" in result

    def test_session_report_generate(self) -> None:
        handler = self.registry.commands["session-report"].handler
        result = asyncio.run(handler("generate demo 50000 128000"))
        assert "demo" in result
        assert "Recommendations" in result


if __name__ == "__main__":
    unittest.main()
