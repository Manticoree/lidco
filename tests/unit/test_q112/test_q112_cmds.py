"""Tests for Q112 CLI commands — Task 696."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.registry import CommandRegistry, SlashCommand
from lidco.cli.commands.q112_cmds import register


def _run(coro):
    return asyncio.run(coro)


class TestQ112CmdsRegistration(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        register(self.registry)

    def test_todo_registered(self):
        cmd = self.registry.get("todo")
        self.assertIsNotNone(cmd)
        self.assertIsInstance(cmd, SlashCommand)

    def test_mode_registered(self):
        cmd = self.registry.get("mode")
        self.assertIsNotNone(cmd)

    def test_spawn_registered(self):
        cmd = self.registry.get("spawn")
        self.assertIsNotNone(cmd)


class TestTodoCommand(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands import q112_cmds
        q112_cmds._state.clear()
        self.registry = CommandRegistry()
        register(self.registry)
        self.handler = self.registry.get("todo").handler

    def test_todo_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_todo_plan(self):
        result = _run(self.handler("plan Build a REST API"))
        self.assertIn("Plan", result)

    def test_todo_board_empty(self):
        result = _run(self.handler("board"))
        # Board may be empty or show something
        self.assertIsInstance(result, str)

    def test_todo_plan_then_board(self):
        _run(self.handler("plan 1. Setup\n2. Build\n3. Test"))
        result = _run(self.handler("board"))
        self.assertIn("Setup", result)

    def test_todo_done(self):
        _run(self.handler("plan 1. Setup\n2. Build"))
        # Get state to know item ids
        result = _run(self.handler("board"))
        # Mark first item done by its id
        # We need to parse the board to get an id
        # For simplicity, just try marking and check no crash
        result = _run(self.handler("done step-1"))
        self.assertIsInstance(result, str)

    def test_todo_done_missing_id(self):
        result = _run(self.handler("done"))
        self.assertIn("Usage", result)

    def test_todo_block(self):
        _run(self.handler("plan 1. Setup\n2. Build"))
        result = _run(self.handler("block step-1 waiting for deps"))
        self.assertIsInstance(result, str)

    def test_todo_block_missing_args(self):
        result = _run(self.handler("block"))
        self.assertIn("Usage", result)

    def test_todo_clear(self):
        _run(self.handler("plan 1. A\n2. B"))
        result = _run(self.handler("clear"))
        self.assertIn("clear", result.lower())

    def test_todo_unknown_sub(self):
        result = _run(self.handler("foobar"))
        self.assertIn("Usage", result)


class TestModeCommand(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands import q112_cmds
        q112_cmds._state.clear()
        self.registry = CommandRegistry()
        register(self.registry)
        self.handler = self.registry.get("mode").handler

    def test_mode_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_mode_switch_to_ask(self):
        result = _run(self.handler("ask"))
        self.assertIn("ask", result.lower())

    def test_mode_switch_to_code(self):
        result = _run(self.handler("code"))
        self.assertIn("code", result.lower())

    def test_mode_switch_to_architect(self):
        result = _run(self.handler("architect"))
        self.assertIn("architect", result.lower())

    def test_mode_switch_to_help(self):
        result = _run(self.handler("help"))
        self.assertIn("help", result.lower())

    def test_mode_invalid(self):
        result = _run(self.handler("invalid"))
        self.assertIn("Invalid", result)

    def test_mode_status(self):
        _run(self.handler("ask"))
        result = _run(self.handler("status"))
        self.assertIn("ask", result.lower())

    def test_mode_status_default(self):
        result = _run(self.handler("status"))
        self.assertIn("code", result.lower())


class TestSpawnCommand(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        register(self.registry)
        self.handler = self.registry.get("spawn").handler

    def test_spawn_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_spawn_with_prompt(self):
        result = _run(self.handler("Analyze this codebase"))
        self.assertIn("session", result.lower())
        self.assertIn("Analyze this codebase", result)

    def test_spawn_returns_session_id(self):
        result = _run(self.handler("Build something"))
        # Should mention a session id
        self.assertIn("session", result.lower())

    def test_spawn_dry_run(self):
        result = _run(self.handler("Test prompt"))
        # dry-run: prints session_id and prompt
        self.assertIn("Test prompt", result)

    def test_spawn_long_prompt(self):
        prompt = "A" * 500
        result = _run(self.handler(prompt))
        self.assertIn("session", result.lower())


if __name__ == "__main__":
    unittest.main()
