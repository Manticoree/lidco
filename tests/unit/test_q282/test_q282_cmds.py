"""Tests for Q282 CLI commands."""
import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands import q282_cmds


class TestQ282Commands(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock()
        q282_cmds._state.clear()
        q282_cmds.register(self.registry)
        self.calls = {c.args[0].name: c.args[0] for c in self.registry.register.call_args_list}

    def _run(self, name, args=""):
        return asyncio.run(self.calls[name].handler(args))

    def test_cot_plan(self):
        result = self._run("cot-plan", "What is recursion and how to use it?")
        self.assertIn("Planned", result)

    def test_cot_plan_summary(self):
        result = self._run("cot-plan", "")
        self.assertIn("total_steps", result)

    def test_cot_execute(self):
        self._run("cot-plan", "Question?")
        result = self._run("cot-execute", "Answer found")
        self.assertIn("Executed", result)

    def test_cot_execute_no_plan(self):
        result = self._run("cot-execute", "")
        self.assertIn("No plan", result)

    def test_cot_optimize(self):
        self._run("cot-plan", "Complex multi-part question. Second part. Third part.")
        result = self._run("cot-optimize", "")
        self.assertIn("Optimized", result)

    def test_cot_optimize_no_plan(self):
        result = self._run("cot-optimize", "")
        self.assertIn("No plan", result)

    def test_cot_visualize_text(self):
        self._run("cot-plan", "Question?")
        result = self._run("cot-visualize", "text")
        self.assertIn("step-", result)

    def test_cot_visualize_mermaid(self):
        self._run("cot-plan", "Question?")
        result = self._run("cot-visualize", "mermaid")
        self.assertIn("graph TD", result)

    def test_cot_visualize_no_plan(self):
        result = self._run("cot-visualize", "")
        self.assertIn("No plan", result)


if __name__ == "__main__":
    unittest.main()
