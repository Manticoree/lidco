"""Tests for Q245 CLI commands."""
from __future__ import annotations

import asyncio
import unittest


def _run(coro):
    return asyncio.run(coro)


class TestModelPoolCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q245_cmds import register

        class FakeRegistry:
            def __init__(self):
                self.commands = {}
            def register(self, cmd):
                self.commands[cmd.name] = cmd

        reg = FakeRegistry()
        register(reg)
        return reg.commands["model-pool"].handler

    def test_add(self):
        h = self._handler()
        result = _run(h("add gpt-4"))
        self.assertIn("Added", result)

    def test_add_no_args(self):
        h = self._handler()
        result = _run(h("add"))
        self.assertIn("Usage", result)

    def test_select(self):
        h = self._handler()
        result = _run(h("select"))
        self.assertIn("No healthy models", result)

    def test_stats(self):
        h = self._handler()
        result = _run(h("stats"))
        self.assertIn("Total", result)

    def test_usage(self):
        h = self._handler()
        result = _run(h(""))
        self.assertIn("Usage", result)


class TestCascadeCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q245_cmds import register

        class FakeRegistry:
            def __init__(self):
                self.commands = {}
            def register(self, cmd):
                self.commands[cmd.name] = cmd

        reg = FakeRegistry()
        register(reg)
        return reg.commands["cascade"].handler

    def test_add(self):
        h = self._handler()
        result = _run(h("add gpt-4 10"))
        self.assertIn("Rule added", result)

    def test_add_no_args(self):
        h = self._handler()
        result = _run(h("add"))
        self.assertIn("Usage", result)

    def test_simulate_no_rules(self):
        h = self._handler()
        result = _run(h("simulate hello"))
        self.assertIn("No cascade rules", result)

    def test_route_no_rules(self):
        h = self._handler()
        result = _run(h("route hello"))
        self.assertIn("failed", result)

    def test_usage(self):
        h = self._handler()
        result = _run(h(""))
        self.assertIn("Usage", result)


class TestEnsembleCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q245_cmds import register

        class FakeRegistry:
            def __init__(self):
                self.commands = {}
            def register(self, cmd):
                self.commands[cmd.name] = cmd

        reg = FakeRegistry()
        register(reg)
        return reg.commands["ensemble"].handler

    def test_add(self):
        h = self._handler()
        result = _run(h("add gpt-4 2.0"))
        self.assertIn("Added", result)

    def test_run_empty(self):
        h = self._handler()
        result = _run(h("run test"))
        self.assertIn("Winner", result)

    def test_list_empty(self):
        h = self._handler()
        result = _run(h("list"))
        self.assertIn("No models", result)

    def test_usage(self):
        h = self._handler()
        result = _run(h(""))
        self.assertIn("Usage", result)


class TestBenchmarkCommand(unittest.TestCase):
    def _handler(self):
        from lidco.cli.commands.q245_cmds import register

        class FakeRegistry:
            def __init__(self):
                self.commands = {}
            def register(self, cmd):
                self.commands[cmd.name] = cmd

        reg = FakeRegistry()
        register(reg)
        return reg.commands["benchmark"].handler

    def test_add(self):
        h = self._handler()
        result = _run(h("add gpt-4 100 0.9 0.01"))
        self.assertIn("Result added", result)

    def test_add_insufficient_args(self):
        h = self._handler()
        result = _run(h("add gpt-4"))
        self.assertIn("Usage", result)

    def test_ranking_empty(self):
        h = self._handler()
        result = _run(h("ranking"))
        self.assertIn("No benchmark results", result)

    def test_compare_insufficient(self):
        h = self._handler()
        result = _run(h("compare only"))
        self.assertIn("Usage", result)

    def test_usage(self):
        h = self._handler()
        result = _run(h(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
