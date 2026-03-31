"""Tests for Q180 CLI commands."""

from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q180_cmds import register_q180_commands


class _FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register(self, cmd: object) -> None:
        self.commands[cmd.name] = cmd  # type: ignore[attr-defined]


class TestQ180Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _FakeRegistry()
        register_q180_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {"review-checklist", "style-check", "security-scan", "perf-check"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    def test_review_checklist_empty(self) -> None:
        handler = self.registry.commands["review-checklist"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_review_checklist_with_diff(self) -> None:
        handler = self.registry.commands["review-checklist"].handler
        result = asyncio.run(handler("except:\n    pass"))
        self.assertIn("Error Handling", result)

    def test_style_check_empty(self) -> None:
        handler = self.registry.commands["style-check"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_style_check_with_code(self) -> None:
        handler = self.registry.commands["style-check"].handler
        result = asyncio.run(handler("from os import *"))
        self.assertIn("wildcard_import", result)

    def test_security_scan_empty(self) -> None:
        handler = self.registry.commands["security-scan"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_security_scan_with_code(self) -> None:
        handler = self.registry.commands["security-scan"].handler
        result = asyncio.run(handler("eval(user_input)"))
        self.assertIn("eval", result)

    def test_perf_check_empty(self) -> None:
        handler = self.registry.commands["perf-check"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_perf_check_with_code(self) -> None:
        handler = self.registry.commands["perf-check"].handler
        result = asyncio.run(handler("count = len([x for x in items if x > 0])"))
        self.assertIn("list_comprehension_to_len", result)


if __name__ == "__main__":
    unittest.main()
