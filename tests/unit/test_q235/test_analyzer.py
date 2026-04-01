"""Tests for thinkback.analyzer."""
from __future__ import annotations

import unittest

from lidco.thinkback.analyzer import ThinkingAnalyzer, Decision, AnalysisResult


class TestDecision(unittest.TestCase):
    def test_frozen(self) -> None:
        d = Decision(text="x")
        with self.assertRaises(AttributeError):
            d.text = "y"  # type: ignore[misc]

    def test_defaults(self) -> None:
        d = Decision(text="x")
        self.assertEqual(d.turn, 0)
        self.assertAlmostEqual(d.confidence, 0.5)
        self.assertEqual(d.category, "")


class TestAnalysisResult(unittest.TestCase):
    def test_frozen(self) -> None:
        ar = AnalysisResult()
        with self.assertRaises(AttributeError):
            ar.chain_length = 5  # type: ignore[misc]

    def test_defaults(self) -> None:
        ar = AnalysisResult()
        self.assertEqual(ar.decisions, ())
        self.assertEqual(ar.uncertainties, ())
        self.assertEqual(ar.chain_length, 0)
        self.assertEqual(ar.summary_text, "")


class TestThinkingAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = ThinkingAnalyzer()

    def test_extract_decisions_ill(self) -> None:
        content = "I'll use Python for this\nOther line"
        decisions = self.analyzer.extract_decisions(content, turn=1)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].turn, 1)
        self.assertIn("Python", decisions[0].text)

    def test_extract_decisions_therefore(self) -> None:
        content = "Therefore we go with option A"
        decisions = self.analyzer.extract_decisions(content)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].category, "conclusion")

    def test_extract_decisions_let_me(self) -> None:
        content = "Let me think about this"
        decisions = self.analyzer.extract_decisions(content)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].category, "exploration")

    def test_extract_decisions_empty(self) -> None:
        self.assertEqual(self.analyzer.extract_decisions("no decisions here"), [])

    def test_detect_uncertainty(self) -> None:
        content = "Maybe this works\nDefinitely correct\nNot sure though"
        uncertain = self.analyzer.detect_uncertainty(content)
        self.assertEqual(len(uncertain), 2)

    def test_detect_uncertainty_none(self) -> None:
        self.assertEqual(self.analyzer.detect_uncertainty("All clear"), [])

    def test_confidence_score_high(self) -> None:
        score = self.analyzer.confidence_score("This is certain")
        self.assertAlmostEqual(score, 1.0)

    def test_confidence_score_low(self) -> None:
        score = self.analyzer.confidence_score("maybe not sure could be uncertain")
        self.assertLess(score, 0.5)

    def test_confidence_score_clamped(self) -> None:
        text = " ".join(["maybe"] * 20)
        score = self.analyzer.confidence_score(text)
        self.assertGreaterEqual(score, 0.0)

    def test_analyze_full(self) -> None:
        content = "I'll try option A\nMaybe it works\nTherefore go with A"
        result = self.analyzer.analyze(content, turn=2)
        self.assertIsInstance(result, AnalysisResult)
        self.assertGreater(len(result.decisions), 0)
        self.assertGreater(len(result.uncertainties), 0)
        self.assertGreater(result.chain_length, 0)

    def test_summarize_chain_single(self) -> None:
        content = "I should do X"
        summary = self.analyzer.summarize_chain(content)
        self.assertIn("I should do X", summary)

    def test_summarize_chain_multiple(self) -> None:
        content = "I'll start with A\nI should also B\nTherefore C"
        summary = self.analyzer.summarize_chain(content)
        self.assertIn("...", summary)

    def test_summary(self) -> None:
        self.analyzer.analyze("I'll do this")
        result = self.analyzer.summary()
        self.assertIn("1 analyses", result)


if __name__ == "__main__":
    unittest.main()
