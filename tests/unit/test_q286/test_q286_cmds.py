"""Tests for Q286 CLI commands."""
from __future__ import annotations

import asyncio
import unittest


def _run(coro):
    return asyncio.run(coro)


def _make_registry():
    from lidco.cli.commands.q286_cmds import register

    class FakeRegistry:
        def __init__(self):
            self.commands = {}
        def register(self, cmd):
            self.commands[cmd.name] = cmd

    reg = FakeRegistry()
    register(reg)
    return reg


class TestToolAnalyzeCommand(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()
        self.handler = self.reg.commands["tool-analyze"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_record(self):
        result = _run(self.handler("record Read 0.5"))
        self.assertIn("Recorded", result)

    def test_score(self):
        result = _run(self.handler("score"))
        self.assertIn("Efficiency score", result)

    def test_unnecessary_empty(self):
        result = _run(self.handler("unnecessary"))
        self.assertIn("No unnecessary", result)

    def test_missed_empty(self):
        result = _run(self.handler("missed"))
        self.assertIn("No missed", result)

    def test_summary(self):
        _run(self.handler("record Read"))
        result = _run(self.handler("summary"))
        self.assertIn("Total calls", result)

    def test_reset(self):
        result = _run(self.handler("reset"))
        self.assertIn("reset", result.lower())

    def test_record_bad_duration(self):
        result = _run(self.handler("record Read abc"))
        self.assertIn("number", result.lower())


class TestToolPlanCommand(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()
        self.handler = self.reg.commands["tool-plan"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_add(self):
        result = _run(self.handler("add Read"))
        self.assertIn("Added", result)

    def test_order(self):
        _run(self.handler("add Read"))
        result = _run(self.handler("order"))
        self.assertIn("Read", result)

    def test_parallel(self):
        _run(self.handler("add Read"))
        _run(self.handler("add Grep"))
        result = _run(self.handler("parallel"))
        self.assertIn("Layer", result)

    def test_optimize(self):
        _run(self.handler("add Read"))
        result = _run(self.handler("optimize"))
        self.assertIn("Ordered", result)

    def test_reset(self):
        result = _run(self.handler("reset"))
        self.assertIn("reset", result.lower())

    def test_add_with_deps(self):
        _run(self.handler("add Read"))
        result = _run(self.handler("add Edit 0"))
        self.assertIn("deps=[0]", result)

    def test_order_empty(self):
        result = _run(self.handler("order"))
        self.assertIn("No calls", result)


class TestCacheAdviceCommand(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()
        self.handler = self.reg.commands["cache-advice"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_record(self):
        result = _run(self.handler("record Read some_result"))
        self.assertIn("Recorded", result)

    def test_suggest_empty(self):
        result = _run(self.handler("suggest"))
        self.assertIn("No caching", result)

    def test_repeated_empty(self):
        result = _run(self.handler("repeated"))
        self.assertIn("No repeated", result)

    def test_savings(self):
        result = _run(self.handler("savings"))
        self.assertIn("Total", result)

    def test_reset(self):
        result = _run(self.handler("reset"))
        self.assertIn("reset", result.lower())

    def test_suggest_with_repeats(self):
        _run(self.handler("record Read"))
        _run(self.handler("record Read"))
        result = _run(self.handler("suggest"))
        self.assertIn("Cache", result)

    def test_repeated_found(self):
        _run(self.handler("record Read"))
        _run(self.handler("record Read"))
        result = _run(self.handler("repeated"))
        self.assertIn("Read", result)


class TestToolComposeCommand(unittest.TestCase):
    def setUp(self):
        self.reg = _make_registry()
        self.handler = self.reg.commands["tool-compose"].handler

    def test_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_add(self):
        result = _run(self.handler("add Read"))
        self.assertIn("Added", result)

    def test_chain(self):
        _run(self.handler("add Read"))
        _run(self.handler("add Edit"))
        result = _run(self.handler("chain"))
        self.assertIn("Read", result)
        self.assertIn("Edit", result)

    def test_list(self):
        _run(self.handler("add Read"))
        result = _run(self.handler("list"))
        self.assertIn("Read", result)

    def test_clear(self):
        _run(self.handler("add Read"))
        result = _run(self.handler("clear"))
        self.assertIn("cleared", result.lower())

    def test_chain_empty(self):
        result = _run(self.handler("chain"))
        self.assertIn("No steps", result)

    def test_list_empty(self):
        result = _run(self.handler("list"))
        self.assertIn("No steps", result)

    def test_add_missing_tool(self):
        result = _run(self.handler("add"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
