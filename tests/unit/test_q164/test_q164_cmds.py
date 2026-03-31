"""Tests for Q164 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest

from lidco.cli.commands import q164_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ164Commands(unittest.TestCase):
    def setUp(self):
        q164_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q164_cmds.register(MockRegistry())
        self.handler = self.registered["sandbox"].handler

    def test_command_registered(self):
        self.assertIn("sandbox", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    def test_on(self):
        result = _run(self.handler("on"))
        self.assertIn("enabled", result.lower())

    def test_off(self):
        _run(self.handler("on"))
        result = _run(self.handler("off"))
        self.assertIn("disabled", result.lower())

    def test_status_disabled(self):
        result = _run(self.handler("status"))
        self.assertIn("disabled", result.lower())

    def test_status_enabled(self):
        _run(self.handler("on"))
        result = _run(self.handler("status"))
        self.assertIn("enabled", result.lower())

    def test_policy_shows_json(self):
        result = _run(self.handler("policy"))
        data = json.loads(result)
        self.assertIn("allowed_paths", data)
        self.assertIn("denied_paths", data)
        self.assertIn("deny_all_network", data)

    def test_violations_no_runner(self):
        result = _run(self.handler("violations"))
        self.assertIn("No sandbox runner", result)

    def test_violations_empty(self):
        _run(self.handler("on"))
        result = _run(self.handler("violations"))
        self.assertIn("No violations", result)

    def test_command_description(self):
        self.assertIn("Q164", self.registered["sandbox"].description)


if __name__ == "__main__":
    unittest.main()
