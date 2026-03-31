"""Tests for Q173 CLI commands — Task 981."""

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q173_cmds import register_q173_commands
from lidco.cli.commands.registry import SlashCommand


class TestQ173Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def fake_register(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = fake_register
        register_q173_commands(self.registry)

    def test_register_commands_count(self):
        self.assertEqual(len(self.registered), 4)

    def test_register_mutate(self):
        self.assertIn("mutate", self.registered)

    def test_register_proptest(self):
        self.assertIn("proptest", self.registered)

    def test_register_coverage_gaps(self):
        self.assertIn("coverage-gaps", self.registered)

    def test_register_test_order(self):
        self.assertIn("test-order", self.registered)

    def test_mutate_no_args(self):
        result = asyncio.run(self.registered["mutate"].handler(""))
        self.assertIn("Usage:", result)

    def test_mutate_with_file(self):
        result = asyncio.run(self.registered["mutate"].handler("src/foo.py"))
        self.assertIn("Mutation testing: src/foo.py", result)
        self.assertIn("max_mutants", result)

    def test_proptest_no_args(self):
        result = asyncio.run(self.registered["proptest"].handler(""))
        self.assertIn("Usage:", result)

    def test_proptest_with_function(self):
        result = asyncio.run(self.registered["proptest"].handler("my_func"))
        self.assertIn("Property test generation for: my_func", result)
        self.assertIn("smoke", result)

    def test_coverage_gaps_default(self):
        result = asyncio.run(self.registered["coverage-gaps"].handler(""))
        self.assertIn("Coverage gap analysis", result)
        self.assertIn("top 10", result)

    def test_coverage_gaps_top_n(self):
        result = asyncio.run(self.registered["coverage-gaps"].handler("--top 5"))
        self.assertIn("top 5", result)

    def test_test_order_no_args(self):
        result = asyncio.run(self.registered["test-order"].handler(""))
        self.assertIn("Usage:", result)

    def test_test_order_changed(self):
        result = asyncio.run(self.registered["test-order"].handler("--changed"))
        self.assertIn("Test ordering based on git changes", result)


if __name__ == "__main__":
    unittest.main()
