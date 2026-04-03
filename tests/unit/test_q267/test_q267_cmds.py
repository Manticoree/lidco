"""Tests for Q267 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

import lidco.cli.commands.q267_cmds as q267_mod
from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def _get_handlers() -> dict[str, object]:
    """Register commands and return handler dict."""
    q267_mod._state.clear()
    reg = CommandRegistry.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    q267_mod.register(reg)
    return {name: cmd.handler for name, cmd in reg._commands.items()}


class TestIncidentDetectCmd(unittest.TestCase):
    def setUp(self):
        self.handlers = _get_handlers()
        self.handler = self.handlers["incident-detect"]

    def test_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_analyze(self):
        events = json.dumps([
            {"type": "data_transfer", "actor": "hacker", "bytes": 500},
        ])
        result = asyncio.run(self.handler(f"analyze {events}"))
        self.assertIn("incident", result.lower())

    def test_analyze_invalid_json(self):
        result = asyncio.run(self.handler("analyze {bad"))
        self.assertIn("Invalid JSON", result)

    def test_analyze_no_args(self):
        result = asyncio.run(self.handler("analyze"))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("No incidents", result)

    def test_severity_no_args(self):
        result = asyncio.run(self.handler("severity"))
        self.assertIn("Usage", result)


class TestIncidentRespondCmd(unittest.TestCase):
    def setUp(self):
        self.handlers = _get_handlers()
        self.handler = self.handlers["incident-respond"]

    def test_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_playbooks(self):
        result = asyncio.run(self.handler("playbooks"))
        self.assertIn("brute_force", result)

    def test_history_empty(self):
        result = asyncio.run(self.handler("history"))
        self.assertIn("No execution history", result)

    def test_execute_no_detector(self):
        result = asyncio.run(self.handler("execute inc1"))
        self.assertIn("No detector", result)


class TestForensicsCmd(unittest.TestCase):
    def setUp(self):
        self.handlers = _get_handlers()
        self.handler = self.handlers["forensics"]

    def test_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_collect(self):
        result = asyncio.run(self.handler("collect inc1 log suspicious login"))
        self.assertIn("Collected evidence", result)

    def test_collect_missing_args(self):
        result = asyncio.run(self.handler("collect inc1"))
        self.assertIn("Usage", result)

    def test_timeline_empty(self):
        result = asyncio.run(self.handler("timeline inc1"))
        self.assertIn("No evidence", result)

    def test_export(self):
        asyncio.run(self.handler("collect inc1 log data"))
        result = asyncio.run(self.handler("export inc1"))
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 1)


class TestIncidentRecoverCmd(unittest.TestCase):
    def setUp(self):
        self.handlers = _get_handlers()
        self.handler = self.handlers["incident-recover"]

    def test_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_plan(self):
        result = asyncio.run(self.handler("plan inc1"))
        self.assertIn("Created recovery plan", result)

    def test_action(self):
        asyncio.run(self.handler("plan inc1"))
        result = asyncio.run(self.handler("action inc1 revert database"))
        self.assertIn("Added action", result)

    def test_execute(self):
        asyncio.run(self.handler("plan inc1"))
        asyncio.run(self.handler("action inc1 revert db"))
        result = asyncio.run(self.handler("execute inc1"))
        self.assertIn("Executed plan", result)
        self.assertIn("completed", result)

    def test_report_no_plan(self):
        result = asyncio.run(self.handler("report missing"))
        self.assertIn("No recovery plan", result)


if __name__ == "__main__":
    unittest.main()
