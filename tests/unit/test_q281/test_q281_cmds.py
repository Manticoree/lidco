"""Tests for Q281 CLI commands."""
import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands import q281_cmds


class TestQ281Commands(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock()
        q281_cmds._state.clear()
        q281_cmds.register(self.registry)
        self.calls = {c.args[0].name: c.args[0] for c in self.registry.register.call_args_list}

    def _run(self, name, args=""):
        return asyncio.run(self.calls[name].handler(args))

    def test_fact_check(self):
        result = self._run("fact-check", "Check src/lidco/app.py for details")
        self.assertIn("Claims", result)

    def test_fact_check_empty(self):
        result = self._run("fact-check", "")
        self.assertIn("Usage", result)

    def test_validate_refs_file(self):
        result = self._run("validate-refs", "file nonexistent.py")
        self.assertIn("NOT FOUND", result)

    def test_validate_refs_summary(self):
        result = self._run("validate-refs", "summary")
        self.assertIn("total_checks", result)

    def test_consistency_check(self):
        result = self._run("consistency", "check Statement A | Statement B")
        self.assertIn("Consistent", result)

    def test_consistency_add_prior(self):
        result = self._run("consistency", "add-prior The sky is blue")
        self.assertIn("Prior statement added", result)

    def test_grounding_add_source(self):
        result = self._run("grounding", "add-source doc1 Python is great")
        self.assertIn("Source added", result)

    def test_grounding_check(self):
        self._run("grounding", "add-source doc1 Python programming language")
        result = self._run("grounding", "check Python is a language")
        self.assertIn("Grounded", result)

    def test_grounding_summary(self):
        result = self._run("grounding", "summary")
        self.assertIn("sources", result)


if __name__ == "__main__":
    unittest.main()
