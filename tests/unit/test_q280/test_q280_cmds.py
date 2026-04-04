"""Tests for Q280 CLI commands."""
import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands import q280_cmds


class TestQ280Commands(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock()
        q280_cmds._state.clear()
        q280_cmds.register(self.registry)
        self.calls = {c.args[0].name: c.args[0] for c in self.registry.register.call_args_list}

    def _run(self, name, args=""):
        return asyncio.run(self.calls[name].handler(args))

    def test_reflect_on(self):
        result = self._run("reflect", "on A detailed response about testing " * 5)
        self.assertIn("Quality", result)

    def test_reflect_history(self):
        self._run("reflect", "on Some response " * 10)
        result = self._run("reflect", "history")
        self.assertIn("1 reflections", result)

    def test_reflect_improvements(self):
        self._run("reflect", "on Short")
        result = self._run("reflect", "improvements")
        self.assertIsInstance(result, str)

    def test_confidence_predict(self):
        result = self._run("confidence", "predict p1 yes 0.9")
        self.assertIn("Prediction recorded", result)

    def test_confidence_resolve(self):
        self._run("confidence", "predict p1 yes 0.9")
        result = self._run("confidence", "resolve p1 yes")
        self.assertIn("correct=True", result)

    def test_confidence_summary(self):
        result = self._run("confidence", "summary")
        self.assertIn("total_predictions", result)

    def test_boundary_assess(self):
        result = self._run("knowledge-boundary", "assess How do Python decorators work?")
        self.assertIn("Category", result)

    def test_boundary_add_domain(self):
        result = self._run("knowledge-boundary", "add-domain python")
        self.assertIn("Added domain", result)

    def test_journal_log(self):
        result = self._run("learning-journal", "log Always validate input")
        self.assertIn("Logged", result)

    def test_journal_search(self):
        self._run("learning-journal", "log Validate input carefully")
        result = self._run("learning-journal", "search validate")
        self.assertIn("Found 1", result)

    def test_journal_summary(self):
        result = self._run("learning-journal", "summary")
        self.assertIn("total_entries", result)


if __name__ == "__main__":
    unittest.main()
