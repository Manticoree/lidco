"""Tests for Q241 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class TestQ241Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}
        def _register(cmd):
            self.registered[cmd.name] = cmd
        self.registry.register = _register
        from lidco.cli.commands.q241_cmds import register
        register(self.registry)

    def test_all_commands_registered(self):
        expected = {"session-save", "session-load", "resume", "session-gc"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_session_save_no_args(self):
        result = _run(self.registered["session-save"].handler(""))
        self.assertIsInstance(result, str)

    def test_session_load_no_args(self):
        result = _run(self.registered["session-load"].handler(""))
        self.assertIn("Usage", result)

    def test_resume_no_args(self):
        result = _run(self.registered["resume"].handler(""))
        self.assertIsInstance(result, str)

    def test_session_gc(self):
        result = _run(self.registered["session-gc"].handler(""))
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
