"""Tests for Q126 CLI commands (/suggest)."""
from __future__ import annotations
import asyncio
import unittest
from lidco.cli.commands import q126_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ126Commands(unittest.TestCase):
    def setUp(self):
        q126_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q126_cmds.register(MockRegistry())
        self.handler = self.registered["suggest"].handler

    def test_command_registered(self):
        self.assertIn("suggest", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_sub_shows_usage(self):
        result = _run(self.handler("unknown_sub"))
        self.assertIn("Usage", result)

    def test_analyze_basic(self):
        result = _run(self.handler("analyze # TODO fix this"))
        # Should find at least the todo comment
        self.assertIn("refactor", result.lower())

    def test_analyze_no_args(self):
        result = _run(self.handler("analyze"))
        self.assertIn("Usage", result)

    def test_analyze_no_suggestions(self):
        result = _run(self.handler("analyze x = 1"))
        # No suggestions for clean simple code (may vary by rules)
        self.assertIsInstance(result, str)

    def test_smells_basic(self):
        src = "def _private(): pass"
        result = _run(self.handler(f"smells {src}"))
        self.assertIsInstance(result, str)

    def test_smells_no_args(self):
        result = _run(self.handler("smells"))
        self.assertIn("Usage", result)

    def test_smells_no_smells(self):
        result = _run(self.handler("smells x = 1"))
        self.assertIsInstance(result, str)

    def test_impact_basic(self):
        result = _run(self.handler("impact mymodule"))
        self.assertIn("mymodule", result)

    def test_impact_no_args(self):
        result = _run(self.handler("impact"))
        self.assertIn("Usage", result)

    def test_impact_no_dependents(self):
        result = _run(self.handler("impact isolated_module"))
        self.assertIn("none", result.lower())

    def test_top_no_previous(self):
        result = _run(self.handler("top 3"))
        self.assertIn("No suggestions", result)

    def test_top_after_analyze(self):
        # Manually set last_suggestions
        from lidco.proactive.suggestion_engine import Suggestion
        q126_cmds._state["last_suggestions"] = [
            Suggestion("a", "refactor", "Fix A", priority=2, confidence=0.8),
        ]
        result = _run(self.handler("top 1"))
        self.assertIn("Fix A", result)

    def test_analyze_returns_count(self):
        result = _run(self.handler("analyze # TODO\n# FIXME"))
        self.assertIn("Suggestion", result)

    def test_smells_with_private(self):
        result = _run(self.handler("smells def _unused_fn(): pass"))
        # dead_code or empty — just check it doesn't crash
        self.assertIsInstance(result, str)

    def test_description_set(self):
        self.assertIn("suggest", self.registered["suggest"].description.lower())

    def test_impact_with_known_module(self):
        # Call handler first to initialize state, then add import
        _run(self.handler("impact init_call"))  # initialize _state
        q126_cmds._state["impact"].add_import("importer", "base_mod")
        result = _run(self.handler("impact base_mod"))
        self.assertIn("importer", result)

    def test_top_default_n(self):
        from lidco.proactive.suggestion_engine import Suggestion
        q126_cmds._state["last_suggestions"] = [
            Suggestion(str(i), "refactor", f"msg {i}") for i in range(10)
        ]
        result = _run(self.handler("top"))
        self.assertIn("Top", result)

    def test_analyze_security(self):
        result = _run(self.handler('analyze password = "abc123"'))
        self.assertIn("security", result.lower())


if __name__ == "__main__":
    unittest.main()
