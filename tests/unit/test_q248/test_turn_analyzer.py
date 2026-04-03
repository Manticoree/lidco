"""Tests for TurnAnalyzer (Q248)."""
from __future__ import annotations

import unittest

from lidco.conversation.turn_analyzer import TurnAnalysis, TurnAnalyzer


def _msgs(*roles_and_contents):
    """Build message list from (role, content) pairs."""
    return [{"role": r, "content": c} for r, c in roles_and_contents]


class TestTurnAnalysis(unittest.TestCase):
    def test_dataclass_fields(self):
        ta = TurnAnalysis(index=0, role="user", token_estimate=10, has_tool_calls=False)
        self.assertEqual(ta.index, 0)
        self.assertEqual(ta.role, "user")
        self.assertEqual(ta.token_estimate, 10)
        self.assertFalse(ta.has_tool_calls)
        self.assertEqual(ta.files_mentioned, [])
        self.assertEqual(ta.score, 0.0)

    def test_frozen(self):
        ta = TurnAnalysis(index=0, role="user", token_estimate=10, has_tool_calls=False)
        with self.assertRaises(AttributeError):
            ta.index = 5  # type: ignore[misc]


class TestAnalyzeTurn(unittest.TestCase):
    def test_basic_user_turn(self):
        msgs = _msgs(("user", "Hello world"))
        analyzer = TurnAnalyzer(msgs)
        ta = analyzer.analyze_turn(0)
        self.assertEqual(ta.index, 0)
        self.assertEqual(ta.role, "user")
        self.assertGreater(ta.token_estimate, 0)
        self.assertFalse(ta.has_tool_calls)

    def test_assistant_with_tool_calls(self):
        msgs = [{"role": "assistant", "content": "Running", "tool_calls": [{"name": "read"}]}]
        analyzer = TurnAnalyzer(msgs)
        ta = analyzer.analyze_turn(0)
        self.assertTrue(ta.has_tool_calls)
        self.assertGreater(ta.score, 0.0)

    def test_file_extraction(self):
        msgs = _msgs(("user", "Please edit src/main.py and tests/test_main.py"))
        ta = TurnAnalyzer(msgs).analyze_turn(0)
        self.assertIn("src/main.py", ta.files_mentioned)
        self.assertIn("tests/test_main.py", ta.files_mentioned)

    def test_index_out_of_range(self):
        analyzer = TurnAnalyzer([])
        with self.assertRaises(IndexError):
            analyzer.analyze_turn(0)

    def test_negative_index(self):
        analyzer = TurnAnalyzer(_msgs(("user", "hi")))
        with self.assertRaises(IndexError):
            analyzer.analyze_turn(-1)

    def test_empty_content(self):
        msgs = [{"role": "assistant", "content": ""}]
        ta = TurnAnalyzer(msgs).analyze_turn(0)
        self.assertEqual(ta.score, 0.0)

    def test_none_content(self):
        msgs = [{"role": "assistant", "content": None}]
        ta = TurnAnalyzer(msgs).analyze_turn(0)
        self.assertEqual(ta.token_estimate, 0)


class TestAnalyzeAll(unittest.TestCase):
    def test_multiple_turns(self):
        msgs = _msgs(("user", "Hello"), ("assistant", "Hi there"), ("user", "Thanks"))
        results = TurnAnalyzer(msgs).analyze_all()
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].role, "user")
        self.assertEqual(results[1].role, "assistant")

    def test_empty(self):
        self.assertEqual(TurnAnalyzer([]).analyze_all(), [])


class TestTokenDeltas(unittest.TestCase):
    def test_deltas(self):
        msgs = _msgs(("user", "Hi"), ("assistant", "Hello there friend"))
        deltas = TurnAnalyzer(msgs).token_deltas()
        self.assertEqual(len(deltas), 2)
        self.assertIsInstance(deltas[0], int)

    def test_empty(self):
        self.assertEqual(TurnAnalyzer([]).token_deltas(), [])


class TestSummary(unittest.TestCase):
    def test_nonempty(self):
        msgs = _msgs(("user", "Hi"), ("assistant", "Hello"))
        s = TurnAnalyzer(msgs).summary()
        self.assertIn("Turns: 2", s)
        self.assertIn("Tokens:", s)

    def test_empty(self):
        self.assertEqual(TurnAnalyzer([]).summary(), "No turns to analyze.")

    def test_tool_turns_counted(self):
        msgs = [
            {"role": "user", "content": "do it"},
            {"role": "assistant", "content": "ok", "tool_calls": [{"name": "x"}]},
        ]
        s = TurnAnalyzer(msgs).summary()
        self.assertIn("Tool turns: 1", s)


if __name__ == "__main__":
    unittest.main()
