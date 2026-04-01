"""Tests for cli/commands/q185_cmds — /feature-dev, /explore-code, /architect, /feature-summary."""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest

from lidco.cli.commands import q185_cmds


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ185Registration(unittest.TestCase):
    def test_registers_four_commands(self):
        reg = _FakeRegistry()
        q185_cmds.register(reg)
        self.assertIn("feature-dev", reg.commands)
        self.assertIn("explore-code", reg.commands)
        self.assertIn("architect", reg.commands)
        self.assertIn("feature-summary", reg.commands)


class TestFeatureDevHandler(unittest.TestCase):
    def setUp(self):
        q185_cmds._state.clear()
        reg = _FakeRegistry()
        q185_cmds.register(reg)
        self._handler = reg.commands["feature-dev"].handler

    def test_no_args_no_workflow(self):
        result = asyncio.run(self._handler(""))
        self.assertIn("No active", result)

    def test_create_workflow(self):
        result = asyncio.run(self._handler("my-feature Add caching"))
        self.assertIn("Created", result)
        self.assertIn("my-feature", result)

    def test_status_after_create(self):
        asyncio.run(self._handler("my-feat some desc"))
        result = asyncio.run(self._handler(""))
        self.assertIn("my-feat", result)
        self.assertIn("discovery", result)

    def test_run_all(self):
        asyncio.run(self._handler("test-feat desc"))
        result = asyncio.run(self._handler("run-all"))
        self.assertIn("Ran 7 phases", result)

    def test_skip_phase(self):
        asyncio.run(self._handler("test-feat desc"))
        result = asyncio.run(self._handler("skip clarification"))
        self.assertIn("skipped", result)

    def test_skip_invalid_phase(self):
        asyncio.run(self._handler("test-feat desc"))
        result = asyncio.run(self._handler("skip nonexistent"))
        self.assertIn("Unknown phase", result)

    def test_next(self):
        asyncio.run(self._handler("test-feat desc"))
        result = asyncio.run(self._handler("next"))
        self.assertIn("discovery", result)
        self.assertIn("done", result)

    def test_next_when_complete(self):
        asyncio.run(self._handler("test-feat desc"))
        asyncio.run(self._handler("run-all"))
        result = asyncio.run(self._handler("next"))
        self.assertIn("complete", result.lower())

    def test_run_all_no_workflow(self):
        result = asyncio.run(self._handler("run-all"))
        self.assertIn("No active", result)

    def test_skip_no_workflow(self):
        result = asyncio.run(self._handler("skip discovery"))
        self.assertIn("No active", result)

    def test_next_no_workflow(self):
        result = asyncio.run(self._handler("next"))
        self.assertIn("No active", result)


class TestExploreCodeHandler(unittest.TestCase):
    def setUp(self):
        reg = _FakeRegistry()
        q185_cmds.register(reg)
        self._handler = reg.commands["explore-code"].handler

    def test_no_args(self):
        result = asyncio.run(self._handler(""))
        self.assertIn("Usage", result)

    def test_explore_real_dir(self):
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "a.py"), "w").close()
            result = asyncio.run(self._handler(td))
            self.assertIn("1 files", result)


class TestArchitectHandler(unittest.TestCase):
    def setUp(self):
        reg = _FakeRegistry()
        q185_cmds.register(reg)
        self._handler = reg.commands["architect"].handler

    def test_no_args(self):
        result = asyncio.run(self._handler(""))
        self.assertIn("Usage", result)

    def test_with_requirements(self):
        result = asyncio.run(self._handler("Add caching layer"))
        self.assertIn("Recommended", result)
        self.assertIn("Blueprint", result)
        self.assertIn("Components", result)


class TestFeatureSummaryHandler(unittest.TestCase):
    def setUp(self):
        q185_cmds._state.clear()
        reg = _FakeRegistry()
        q185_cmds.register(reg)
        self._dev = reg.commands["feature-dev"].handler
        self._summary = reg.commands["feature-summary"].handler

    def test_no_workflow(self):
        result = asyncio.run(self._summary(""))
        self.assertIn("No active", result)

    def test_summary_after_create(self):
        asyncio.run(self._dev("test-feat some description"))
        result = asyncio.run(self._summary(""))
        self.assertIn("test-feat", result)
        self.assertIn("No phases executed", result)

    def test_summary_after_run_all(self):
        asyncio.run(self._dev("test-feat desc"))
        asyncio.run(self._dev("run-all"))
        result = asyncio.run(self._summary(""))
        self.assertIn("test-feat", result)
        self.assertIn("Complete: True", result)


if __name__ == "__main__":
    unittest.main()
