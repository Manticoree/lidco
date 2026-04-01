"""Tests for cli.commands.q191_cmds — /multi-edit, /batch-write, /edit-plan, /transaction."""
from __future__ import annotations

import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from lidco.cli.commands.q191_cmds import register_q191_commands


def _make_registry():
    registry = MagicMock()
    registry._commands = {}

    def fake_register(cmd):
        registry._commands[cmd.name] = cmd

    registry.register = fake_register
    return registry


def _run(coro):
    return asyncio.run(coro)


class TestQ191Registration(unittest.TestCase):
    def test_commands_registered(self):
        registry = _make_registry()
        register_q191_commands(registry)
        expected = {"multi-edit", "batch-write", "edit-plan", "transaction"}
        self.assertEqual(set(registry._commands.keys()), expected)


class TestMultiEditHandler(unittest.TestCase):
    def test_no_args_shows_usage(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["multi-edit"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_missing_file(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["multi-edit"].handler
        result = _run(handler("/nonexistent/file.py"))
        self.assertIn("Error", result)

    def test_valid_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("hello world")
            f.flush()
            path = f.name
        try:
            registry = _make_registry()
            register_q191_commands(registry)
            handler = registry._commands["multi-edit"].handler
            result = _run(handler(path))
            self.assertIn("Multi-edit session created", result)
            self.assertIn("11 chars", result)
        finally:
            os.unlink(path)


class TestBatchWriteHandler(unittest.TestCase):
    def test_no_args_shows_usage(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["batch-write"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_dry_run(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["batch-write"].handler
        result = _run(handler("dry-run"))
        self.assertIn("0 operations", result)

    def test_unknown_subcommand(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["batch-write"].handler
        result = _run(handler("invalid"))
        self.assertIn("Unknown", result)


class TestEditPlanHandler(unittest.TestCase):
    def test_no_args_shows_usage(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["edit-plan"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_with_args(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["edit-plan"].handler
        result = _run(handler("some_file.py"))
        self.assertIn("0 edits", result)


class TestTransactionHandler(unittest.TestCase):
    def test_no_args_shows_usage(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["transaction"].handler
        result = _run(handler(""))
        self.assertIn("Usage", result)

    def test_status(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["transaction"].handler
        result = _run(handler("status"))
        self.assertIn("No active transaction", result)

    def test_unknown_subcommand(self):
        registry = _make_registry()
        register_q191_commands(registry)
        handler = registry._commands["transaction"].handler
        result = _run(handler("invalid"))
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()
