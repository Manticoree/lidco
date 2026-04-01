"""Tests for lidco.cli.commands.q220_cmds."""
from __future__ import annotations

import asyncio

import pytest


def _run(coro):
    return asyncio.run(coro)


class TestAgentDagCommand:
    def test_no_args(self) -> None:
        from lidco.cli.commands.q220_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("agent-dag")
        assert cmd is not None
        result = _run(cmd.handler(""))
        assert "Usage" in result

    def test_with_args(self) -> None:
        from lidco.cli.commands.q220_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("agent-dag")
        result = _run(cmd.handler("nodeA planner"))
        assert "1 nodes" in result


class TestAgentResultsCommand:
    def test_no_args(self) -> None:
        from lidco.cli.commands.q220_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("agent-results")
        result = _run(cmd.handler(""))
        assert "Usage" in result

    def test_with_args(self) -> None:
        from lidco.cli.commands.q220_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("agent-results")
        result = _run(cmd.handler("myagent some output here"))
        assert "1 agents" in result


class TestAgentBudgetCommand:
    def test_no_args(self) -> None:
        from lidco.cli.commands.q220_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("agent-budget")
        result = _run(cmd.handler(""))
        assert "Usage" in result

    def test_with_args(self) -> None:
        from lidco.cli.commands.q220_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("agent-budget")
        result = _run(cmd.handler("1000 agentA,agentB"))
        assert "1000 tokens" in result


class TestAgentCancelCommand:
    def test_no_args(self) -> None:
        from lidco.cli.commands.q220_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("agent-cancel")
        result = _run(cmd.handler(""))
        assert "Usage" in result

    def test_with_args(self) -> None:
        from lidco.cli.commands.q220_cmds import register
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry()
        register(reg)
        cmd = reg.get("agent-cancel")
        result = _run(cmd.handler("agent1"))
        assert "agent1" in result
