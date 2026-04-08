"""Tests for lidco.cli.commands.q314_cmds — CLI wiring."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler: object) -> None:
        self.commands[name] = (desc, handler)


class TestQ314CommandRegistration(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q314_cmds import register_q314_commands

        self.registry = _FakeRegistry()
        register_q314_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {"flaky-detect", "flaky-analyze", "flaky-quarantine", "flaky-dashboard"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    def test_descriptions_non_empty(self) -> None:
        for name, (desc, _) in self.registry.commands.items():
            self.assertTrue(len(desc) > 0, f"{name} has empty description")


class TestFlakyDetectHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q314_cmds import register_q314_commands

        self.registry = _FakeRegistry()
        register_q314_commands(self.registry)
        self.handler = self.registry.commands["flaky-detect"][1]

    def test_empty_args(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Flaky Detection", result)
        self.assertIn("Total tests: 0", result)

    def test_with_flags(self) -> None:
        result = asyncio.run(self.handler("--min-runs 5 --threshold 0.9"))
        self.assertIn("min_runs=5", result)
        self.assertIn("threshold=0.9", result)

    def test_with_path(self) -> None:
        result = asyncio.run(self.handler("./tests"))
        self.assertIn("Flaky Detection", result)


class TestFlakyAnalyzeHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q314_cmds import register_q314_commands

        self.registry = _FakeRegistry()
        register_q314_commands(self.registry)
        self.handler = self.registry.commands["flaky-analyze"][1]

    def test_empty_args(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Flaky Analysis", result)
        self.assertIn("Analyzed: 0", result)

    def test_with_flags(self) -> None:
        result = asyncio.run(self.handler("--min-runs 5 --timing-threshold 200"))
        self.assertIn("min_runs=5", result)


class TestFlakyQuarantineHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q314_cmds import register_q314_commands

        self.registry = _FakeRegistry()
        register_q314_commands(self.registry)
        self.handler = self.registry.commands["flaky-quarantine"][1]

    def test_status_default(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Quarantine Status:", result)
        self.assertIn("Total: 0", result)

    def test_add_action(self) -> None:
        result = asyncio.run(self.handler("add test_x --reason flaky"))
        self.assertIn("Quarantined:", result)
        self.assertIn("test_x", result)

    def test_release_nonexistent(self) -> None:
        result = asyncio.run(self.handler("release nonexistent"))
        self.assertIn("not found", result)

    def test_override_nonexistent(self) -> None:
        result = asyncio.run(self.handler("override nonexistent"))
        self.assertIn("not found", result)


class TestFlakyDashboardHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q314_cmds import register_q314_commands

        self.registry = _FakeRegistry()
        register_q314_commands(self.registry)
        self.handler = self.registry.commands["flaky-dashboard"][1]

    def test_empty_args(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Flaky Test Dashboard", result)

    def test_with_top(self) -> None:
        result = asyncio.run(self.handler("--top 5"))
        self.assertIn("Flaky Test Dashboard", result)


if __name__ == "__main__":
    unittest.main()
