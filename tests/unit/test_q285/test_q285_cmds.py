"""Tests for lidco.cli.commands.q285_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q285_cmds import register_q285_commands, _state


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ285Commands(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q285_commands(self.registry)
        # Reset shared state between tests
        _state["last_goal"] = None
        _state["last_subtasks"] = None
        _state["monitor"] = None

    def test_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("goal", names)
        self.assertIn("subtasks", names)
        self.assertIn("goal-progress", names)
        self.assertIn("validate-goal", names)

    def test_goal_empty(self):
        handler = self.registry.commands["goal"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_goal_parse(self):
        handler = self.registry.commands["goal"].handler
        result = asyncio.run(handler("Build login page\n- Email field\n- Password field"))
        self.assertIn("Goal:", result)
        self.assertIn("Criteria: 2", result)

    def test_subtasks_no_goal(self):
        handler = self.registry.commands["subtasks"].handler
        result = asyncio.run(handler(""))
        self.assertIn("No goal set", result)

    def test_subtasks_generate(self):
        goal_handler = self.registry.commands["goal"].handler
        asyncio.run(goal_handler("Auth\n- Login\n- Logout"))
        handler = self.registry.commands["subtasks"].handler
        result = asyncio.run(handler("generate"))
        self.assertIn("Generated", result)
        self.assertIn("subtask", result)

    def test_subtasks_graph(self):
        goal_handler = self.registry.commands["goal"].handler
        asyncio.run(goal_handler("Auth\n- Login\n- Logout"))
        handler = self.registry.commands["subtasks"].handler
        result = asyncio.run(handler("graph"))
        self.assertIn("Dependency graph", result)

    def test_subtasks_effort(self):
        goal_handler = self.registry.commands["goal"].handler
        asyncio.run(goal_handler("Auth\n- Login\n- Logout"))
        handler = self.registry.commands["subtasks"].handler
        result = asyncio.run(handler("effort"))
        self.assertIn("effort", result.lower())

    def test_goal_progress_status_empty(self):
        handler = self.registry.commands["goal-progress"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Progress", result)

    def test_goal_progress_update(self):
        goal_handler = self.registry.commands["goal"].handler
        asyncio.run(goal_handler("Auth\n- Login\n- Logout"))
        subtasks_handler = self.registry.commands["subtasks"].handler
        asyncio.run(subtasks_handler("generate"))
        handler = self.registry.commands["goal-progress"].handler
        # Get a subtask id from state
        subtasks = _state["last_subtasks"]
        sid = subtasks[0].id
        result = asyncio.run(handler(f"update {sid} done"))
        self.assertIn("Updated", result)

    def test_goal_progress_blocker(self):
        handler = self.registry.commands["goal-progress"].handler
        result = asyncio.run(handler("blocker Need API key"))
        self.assertIn("Blocker added", result)

    def test_validate_goal_no_goal(self):
        handler = self.registry.commands["validate-goal"].handler
        result = asyncio.run(handler(""))
        self.assertIn("No goal set", result)

    def test_validate_goal_full(self):
        goal_handler = self.registry.commands["goal"].handler
        asyncio.run(goal_handler("Auth\n- Login\n- Logout"))
        subtasks_handler = self.registry.commands["subtasks"].handler
        asyncio.run(subtasks_handler("generate"))
        # Initialize monitor
        progress_handler = self.registry.commands["goal-progress"].handler
        asyncio.run(progress_handler("status"))
        handler = self.registry.commands["validate-goal"].handler
        result = asyncio.run(handler("full"))
        self.assertIn("Validation", result)

    def test_validate_goal_partial(self):
        goal_handler = self.registry.commands["goal"].handler
        asyncio.run(goal_handler("Auth\n- Login\n- Logout"))
        handler = self.registry.commands["validate-goal"].handler
        result = asyncio.run(handler("partial 0.5"))
        self.assertIn("validation", result.lower())


if __name__ == "__main__":
    unittest.main()
