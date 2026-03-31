"""Tests for lidco.cli.commands.q162_cmds — Q162 Task 926."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q162_cmds import register, _state


class FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register(self, cmd) -> None:
        self.commands[cmd.name] = cmd


class TestQ162CommandRegistration(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()
        self.registry = FakeRegistry()
        register(self.registry)

    def test_btw_registered(self) -> None:
        self.assertIn("btw", self.registry.commands)

    def test_plan_mode_registered(self) -> None:
        self.assertIn("plan-mode", self.registry.commands)

    def test_workflows_registered(self) -> None:
        self.assertIn("workflows", self.registry.commands)

    def test_model_alias_registered(self) -> None:
        self.assertIn("model-alias", self.registry.commands)


class TestBtwHandler(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()
        self.registry = FakeRegistry()
        register(self.registry)
        self.handler = self.registry.commands["btw"].handler

    def test_ask(self) -> None:
        result = asyncio.run(self.handler("What is Python?"))
        self.assertIn("Python", result)
        self.assertIn("tokens", result)

    def test_empty(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_history(self) -> None:
        asyncio.run(self.handler("Q1"))
        result = asyncio.run(self.handler("history"))
        self.assertIn("Q1", result)

    def test_clear(self) -> None:
        asyncio.run(self.handler("Q1"))
        result = asyncio.run(self.handler("clear"))
        self.assertIn("cleared", result)


class TestPlanModeHandler(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()
        self.registry = FakeRegistry()
        register(self.registry)
        self.handler = self.registry.commands["plan-mode"].handler

    def test_on(self) -> None:
        result = asyncio.run(self.handler("on"))
        self.assertIn("activated", result)

    def test_off(self) -> None:
        asyncio.run(self.handler("on"))
        result = asyncio.run(self.handler("off"))
        self.assertIn("deactivated", result)

    def test_status(self) -> None:
        result = asyncio.run(self.handler("status"))
        self.assertIn("inactive", result)

    def test_status_active(self) -> None:
        asyncio.run(self.handler("on"))
        result = asyncio.run(self.handler("status"))
        self.assertIn("active", result)

    def test_show_empty(self) -> None:
        result = asyncio.run(self.handler("show"))
        self.assertIn("No plan", result)

    def test_clear(self) -> None:
        result = asyncio.run(self.handler("clear"))
        self.assertIn("cleared", result)

    def test_usage(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestWorkflowsHandler(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()
        self.registry = FakeRegistry()
        register(self.registry)
        self.handler = self.registry.commands["workflows"].handler

    def test_list_empty(self) -> None:
        result = asyncio.run(self.handler("list"))
        self.assertIn("No workflows", result)

    def test_run_missing(self) -> None:
        result = asyncio.run(self.handler("run nonexistent"))
        self.assertIn("not found", result)

    def test_run_no_name(self) -> None:
        result = asyncio.run(self.handler("run"))
        self.assertIn("Usage", result)

    def test_default_lists(self) -> None:
        result = asyncio.run(self.handler(""))
        # Either lists or says no workflows
        self.assertTrue("Workflows" in result or "No workflows" in result)


class TestModelAliasHandler(unittest.TestCase):
    def setUp(self) -> None:
        _state.clear()
        self.registry = FakeRegistry()
        register(self.registry)
        self.handler = self.registry.commands["model-alias"].handler

    def test_list_defaults(self) -> None:
        result = asyncio.run(self.handler("list"))
        self.assertIn("claude-sonnet", result)
        self.assertIn("claude-opus", result)

    def test_add(self) -> None:
        result = asyncio.run(self.handler("add fast openai/gpt-4o-mini"))
        self.assertIn("added", result)

    def test_remove(self) -> None:
        result = asyncio.run(self.handler("remove s"))
        self.assertIn("removed", result)

    def test_remove_missing(self) -> None:
        result = asyncio.run(self.handler("remove nonexistent"))
        self.assertIn("not found", result)

    def test_resolve(self) -> None:
        result = asyncio.run(self.handler("resolve s"))
        self.assertIn("claude-sonnet", result)

    def test_usage(self) -> None:
        result = asyncio.run(self.handler("unknown-sub"))
        self.assertIn("Usage", result)

    def test_add_no_args(self) -> None:
        result = asyncio.run(self.handler("add"))
        self.assertIn("Usage", result)

    def test_default_shows_list(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("aliases", result.lower())


if __name__ == "__main__":
    unittest.main()
