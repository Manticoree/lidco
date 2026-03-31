"""Tests for Q140 DidYouMean."""
from __future__ import annotations

import unittest

from lidco.input.did_you_mean import DidYouMean, Suggestion


class TestSuggestion(unittest.TestCase):
    def test_dataclass_fields(self):
        s = Suggestion(original="comit", suggested="commit", score=0.9, context="command")
        self.assertEqual(s.original, "comit")
        self.assertEqual(s.suggested, "commit")
        self.assertAlmostEqual(s.score, 0.9)
        self.assertEqual(s.context, "command")


class TestDidYouMean(unittest.TestCase):
    def setUp(self):
        self.commands = ["commit", "config", "context", "clear", "help", "status"]
        self.dym = DidYouMean(self.commands)

    def test_exact_match(self):
        results = self.dym.suggest("commit")
        self.assertTrue(any(s.suggested == "commit" for s in results))
        self.assertAlmostEqual(results[0].score, 1.0)

    def test_close_match(self):
        results = self.dym.suggest("comit")
        self.assertTrue(any(s.suggested == "commit" for s in results))

    def test_no_match(self):
        results = self.dym.suggest("zzzzzzzzz")
        self.assertEqual(results, [])

    def test_max_results(self):
        results = self.dym.suggest("co", max_results=2)
        self.assertLessEqual(len(results), 2)

    def test_scores_sorted_descending(self):
        results = self.dym.suggest("con")
        scores = [s.score for s in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_format_suggestion_found(self):
        text = self.dym.format_suggestion("comit")
        self.assertIn("Did you mean", text)
        self.assertIn("commit", text)

    def test_format_suggestion_not_found(self):
        text = self.dym.format_suggestion("zzzzzzzzz")
        self.assertIn("Unknown command", text)

    def test_add_command(self):
        self.dym.add_command("deploy")
        results = self.dym.suggest("deploy")
        self.assertTrue(any(s.suggested == "deploy" for s in results))

    def test_add_command_no_duplicate(self):
        self.dym.add_command("commit")
        count = sum(1 for c in self.dym._commands if c == "commit")
        self.assertEqual(count, 1)

    def test_remove_command(self):
        self.dym.remove_command("commit")
        results = self.dym.suggest("commit")
        self.assertFalse(any(s.suggested == "commit" for s in results))

    def test_closest_found(self):
        result = self.dym.closest("comit")
        self.assertEqual(result, "commit")

    def test_closest_none(self):
        result = self.dym.closest("zzzzzzzzz")
        self.assertIsNone(result)

    def test_empty_commands(self):
        dym = DidYouMean([])
        self.assertIsNone(dym.closest("anything"))

    def test_slash_prefix_stripped(self):
        results = self.dym.suggest("/comit")
        self.assertTrue(any(s.suggested == "commit" for s in results))

    def test_suggestion_context(self):
        results = self.dym.suggest("comit")
        for s in results:
            self.assertEqual(s.context, "command")

    def test_original_preserved(self):
        results = self.dym.suggest("comit")
        for s in results:
            self.assertEqual(s.original, "comit")

    def test_multiple_close_matches(self):
        results = self.dym.suggest("config")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].suggested, "config")

    def test_single_char_input(self):
        results = self.dym.suggest("c")
        # Should return something or empty, no crash
        self.assertIsInstance(results, list)

    def test_format_with_slash(self):
        text = self.dym.format_suggestion("/statu")
        self.assertIn("/", text)


if __name__ == "__main__":
    unittest.main()
