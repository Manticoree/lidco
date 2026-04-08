"""Tests for Q343 CLI commands (Task 5)."""
from __future__ import annotations

import asyncio
import unittest


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = (description, handler)


class TestQ343Registration(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q343_cmds import register_q343_commands
        self.reg = _FakeRegistry()
        register_q343_commands(self.reg)

    def test_all_commands_registered(self):
        expected = {
            "thread-safety",
            "deadlock-detect",
            "queue-guard",
            "resource-cleanup",
        }
        self.assertEqual(set(self.reg.commands.keys()), expected)

    def test_all_descriptions_non_empty(self):
        for name, (desc, _) in self.reg.commands.items():
            self.assertTrue(len(desc) > 0, f"'{name}' has empty description")


class TestThreadSafetyCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q343_cmds import register_q343_commands
        reg = _FakeRegistry()
        register_q343_commands(reg)
        self.handler = reg.commands["thread-safety"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_source_with_mutation_produces_report(self):
        src = "_cache = {}\ndef f(k,v):\n    _cache[k] = v\n"
        result = _run(self.handler(src))
        self.assertIn("Thread Safety Analysis", result)

    def test_clean_source_shows_total_issues(self):
        result = _run(self.handler("x = 1\n"))
        self.assertIn("Total issues", result)


class TestDeadlockDetectCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q343_cmds import register_q343_commands
        reg = _FakeRegistry()
        register_q343_commands(reg)
        self.handler = reg.commands["deadlock-detect"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_blocking_call_produces_report(self):
        src = "import asyncio, time\nasync def bad():\n    time.sleep(1)\n"
        result = _run(self.handler(src))
        self.assertIn("Deadlock Detection", result)

    def test_total_issues_in_output(self):
        result = _run(self.handler("x = 1\n"))
        self.assertIn("Total issues", result)


class TestQueueGuardCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q343_cmds import register_q343_commands
        reg = _FakeRegistry()
        register_q343_commands(reg)
        self.handler = reg.commands["queue-guard"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_unbounded_queue_produces_report(self):
        src = "import queue\nq = queue.Queue()\n"
        result = _run(self.handler(src))
        self.assertIn("Queue Overflow Guard", result)

    def test_total_issues_in_output(self):
        result = _run(self.handler("x = 1\n"))
        self.assertIn("Total issues", result)


class TestResourceCleanupCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q343_cmds import register_q343_commands
        reg = _FakeRegistry()
        register_q343_commands(reg)
        self.handler = reg.commands["resource-cleanup"][1]

    def test_empty_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_bare_open_call_produces_report(self):
        src = "f = open('file.txt')\n"
        result = _run(self.handler(src))
        self.assertIn("Resource Cleanup", result)

    def test_total_issues_in_output(self):
        result = _run(self.handler("x = 1\n"))
        self.assertIn("Total issues", result)

    def test_sqlite_connection_produces_report(self):
        src = "import sqlite3\nconn = sqlite3.connect('db.sqlite3')\n"
        result = _run(self.handler(src))
        self.assertIn("Resource Cleanup", result)
