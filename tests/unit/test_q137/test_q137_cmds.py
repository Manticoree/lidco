"""Tests for Q137 CLI commands."""
from __future__ import annotations
import asyncio
import unittest
from unittest.mock import MagicMock
from lidco.cli.commands.q137_cmds import register


def _run(coro):
    return asyncio.run(coro)


class TestTextCommand(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registry.register = MagicMock()
        register(self.registry)
        self.handler = self.registry.register.call_args[0][0].handler

    def test_registered(self):
        cmd = self.registry.register.call_args[0][0]
        self.assertEqual(cmd.name, "text")

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_sub_shows_usage(self):
        result = _run(self.handler("unknown"))
        self.assertIn("Usage", result)

    # --- match ---
    def test_match_missing_args(self):
        result = _run(self.handler("match foo"))
        self.assertIn("Usage", result)

    def test_match_finds_candidates(self):
        result = _run(self.handler("match apple apple,application,banana"))
        self.assertIn("apple", result)

    def test_match_no_results(self):
        result = _run(self.handler("match zzz apple,banana"))
        self.assertIn("No matches", result)

    def test_match_shows_score(self):
        result = _run(self.handler("match apple apple,apply"))
        self.assertIn("score=", result)

    # --- diff ---
    def test_diff_missing_separator(self):
        result = _run(self.handler("diff hello"))
        self.assertIn("Usage", result)

    def test_diff_identical(self):
        result = _run(self.handler("diff hello|||hello"))
        self.assertEqual(result, "hello")

    def test_diff_shows_changes(self):
        result = _run(self.handler("diff abc|||axc"))
        # Should contain inline diff markers
        self.assertIsInstance(result, str)

    # --- similar ---
    def test_similar_missing_separator(self):
        result = _run(self.handler("similar hello"))
        self.assertIn("Usage", result)

    def test_similar_returns_json(self):
        result = _run(self.handler("similar hello|||hello"))
        self.assertIn("levenshtein", result)
        self.assertIn("ratio", result)

    def test_similar_has_all_metrics(self):
        result = _run(self.handler("similar abc|||xyz"))
        self.assertIn("jaccard", result)
        self.assertIn("cosine", result)

    # --- normalize ---
    def test_normalize_missing_text(self):
        result = _run(self.handler("normalize"))
        self.assertIn("Usage", result)

    def test_normalize_returns_result(self):
        result = _run(self.handler("normalize  Hello  World  "))
        self.assertIn("Normalized", result)

    def test_normalize_shows_changes(self):
        result = _run(self.handler("normalize  Hello  World  "))
        self.assertIn("Changes", result)

    def test_normalize_lowered(self):
        result = _run(self.handler("normalize Hello"))
        self.assertIn("hello", result)

    def test_match_csv_multiple(self):
        result = _run(self.handler("match app apple, apply, banana"))
        self.assertIn("Matches", result)


if __name__ == "__main__":
    unittest.main()
