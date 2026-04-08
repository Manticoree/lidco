"""Tests for lidco.cli.commands.q336_cmds — Q336 slash commands."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _run(coro):  # noqa: ANN001, ANN202
    return asyncio.run(coro)


class _FakeRegistry:
    """Minimal registry mock that stores registered handlers."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = (description, handler)


class TestRegisterQ336Commands(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q336_cmds import register_q336_commands

        self.registry = _FakeRegistry()
        register_q336_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {"dig-history", "decode-legacy", "migration-advice", "find-dead-features"}
        self.assertEqual(set(self.registry.commands.keys()), expected)


class TestDigHistoryHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q336_cmds import register_q336_commands

        self.registry = _FakeRegistry()
        register_q336_commands(self.registry)
        _, self.handler = self.registry.commands["dig-history"]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_timeline_no_target(self) -> None:
        result = _run(self.handler("timeline"))
        self.assertIn("Usage", result)

    def test_timeline_with_target(self) -> None:
        result = _run(self.handler("timeline auth.py"))
        self.assertIn("auth.py", result)

    def test_decisions(self) -> None:
        result = _run(self.handler("decisions"))
        self.assertIn("No design decisions", result)

    def test_intent_no_target(self) -> None:
        result = _run(self.handler("intent"))
        self.assertIn("Usage", result)

    def test_intent_with_target(self) -> None:
        result = _run(self.handler("intent main.py"))
        self.assertIn("No history found", result)

    def test_hotfiles_default(self) -> None:
        result = _run(self.handler("hotfiles"))
        self.assertIn("No file change data", result)

    def test_hotfiles_with_n(self) -> None:
        result = _run(self.handler("hotfiles 5"))
        self.assertIn("No file change data", result)

    def test_unknown_subcommand(self) -> None:
        result = _run(self.handler("bogus"))
        self.assertIn("Unknown subcommand", result)


class TestDecodeLegacyHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q336_cmds import register_q336_commands

        self.registry = _FakeRegistry()
        register_q336_commands(self.registry)
        _, self.handler = self.registry.commands["decode-legacy"]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_explain_no_pattern(self) -> None:
        result = _run(self.handler("explain"))
        self.assertIn("Usage", result)

    def test_explain_known(self) -> None:
        result = _run(self.handler("explain bare-except"))
        self.assertIn("bare-except", result)

    def test_decode_source_text(self) -> None:
        result = _run(self.handler("x = eval(data)"))
        self.assertIn("Decoded", result)


class TestMigrationAdviceHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q336_cmds import register_q336_commands

        self.registry = _FakeRegistry()
        register_q336_commands(self.registry)
        _, self.handler = self.registry.commands["migration-advice"]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_assess(self) -> None:
        result = _run(self.handler("assess"))
        self.assertIn("No migration risks", result)

    def test_plan_default(self) -> None:
        result = _run(self.handler("plan"))
        self.assertIn("Migration Plan", result)

    def test_plan_named(self) -> None:
        result = _run(self.handler("plan my-migration"))
        self.assertIn("my-migration", result)

    def test_unknown_subcommand(self) -> None:
        result = _run(self.handler("bogus"))
        self.assertIn("Unknown subcommand", result)


class TestFindDeadFeaturesHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q336_cmds import register_q336_commands

        self.registry = _FakeRegistry()
        register_q336_commands(self.registry)
        _, self.handler = self.registry.commands["find-dead-features"]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_scan(self) -> None:
        result = _run(self.handler("scan"))
        self.assertIn("Dead Feature Report", result)

    def test_summary(self) -> None:
        result = _run(self.handler("summary"))
        self.assertIn("Dead Feature Report", result)

    def test_unknown_subcommand(self) -> None:
        result = _run(self.handler("bogus"))
        self.assertIn("Unknown subcommand", result)


if __name__ == "__main__":
    unittest.main()
