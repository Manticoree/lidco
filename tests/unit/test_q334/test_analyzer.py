"""Tests for lidco.writing.analyzer — WritingAnalyzer."""

from __future__ import annotations

import unittest

from lidco.writing.analyzer import (
    AnalysisResult,
    ConsistencyIssue,
    JargonMatch,
    ReadabilityScore,
    ToneResult,
    WritingAnalyzer,
)


class TestReadabilityScore(unittest.TestCase):
    def test_label_easy(self):
        s = ReadabilityScore(grade_level=3.0, reading_ease=85.0, avg_sentence_length=10.0, avg_syllables_per_word=1.2)
        self.assertEqual(s.label, "easy")

    def test_label_standard(self):
        s = ReadabilityScore(grade_level=7.0, reading_ease=65.0, avg_sentence_length=15.0, avg_syllables_per_word=1.5)
        self.assertEqual(s.label, "standard")

    def test_label_moderate(self):
        s = ReadabilityScore(grade_level=10.0, reading_ease=45.0, avg_sentence_length=20.0, avg_syllables_per_word=1.8)
        self.assertEqual(s.label, "moderate")

    def test_label_difficult(self):
        s = ReadabilityScore(grade_level=14.0, reading_ease=20.0, avg_sentence_length=25.0, avg_syllables_per_word=2.2)
        self.assertEqual(s.label, "difficult")


class TestWritingAnalyzerReadability(unittest.TestCase):
    def setUp(self):
        self.analyzer = WritingAnalyzer()

    def test_empty_text(self):
        score = self.analyzer.readability("")
        self.assertEqual(score.grade_level, 0.0)
        self.assertEqual(score.reading_ease, 100.0)

    def test_simple_text(self):
        text = "The cat sat on the mat. The dog ran fast."
        score = self.analyzer.readability(text)
        self.assertIsInstance(score, ReadabilityScore)
        self.assertGreater(score.reading_ease, 50.0)
        self.assertGreater(score.avg_sentence_length, 0)

    def test_complex_text(self):
        text = (
            "The implementation of sophisticated algorithmic paradigms necessitates "
            "comprehensive understanding of computational complexity theory."
        )
        score = self.analyzer.readability(text)
        self.assertIsInstance(score, ReadabilityScore)
        self.assertGreater(score.avg_syllables_per_word, 1.5)


class TestWritingAnalyzerJargon(unittest.TestCase):
    def setUp(self):
        self.analyzer = WritingAnalyzer()

    def test_no_jargon(self):
        text = "The function returns a list of items."
        matches = self.analyzer.detect_jargon(text)
        self.assertEqual(len(matches), 0)

    def test_detect_leverage(self):
        text = "We should leverage the existing API."
        matches = self.analyzer.detect_jargon(text)
        self.assertTrue(any(m.term == "leverage" for m in matches))
        self.assertTrue(any(m.suggestion == "use" for m in matches))

    def test_detect_multiple_jargon(self):
        text = "We need to leverage synergy and utilize paradigm shifts."
        matches = self.analyzer.detect_jargon(text)
        terms = {m.term for m in matches}
        self.assertIn("leverage", terms)
        self.assertIn("synergy", terms)
        self.assertIn("utilize", terms)
        self.assertIn("paradigm", terms)

    def test_jargon_line_numbers(self):
        text = "Line one.\nWe leverage this.\nLine three."
        matches = self.analyzer.detect_jargon(text)
        self.assertTrue(any(m.line == 2 for m in matches))

    def test_custom_jargon_dict(self):
        analyzer = WritingAnalyzer(jargon_dict={"foo": "bar"})
        matches = analyzer.detect_jargon("We should foo the system.")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].suggestion, "bar")


class TestWritingAnalyzerConsistency(unittest.TestCase):
    def setUp(self):
        self.analyzer = WritingAnalyzer()

    def test_no_issues(self):
        text = "The frontend is fast. The frontend is good."
        issues = self.analyzer.check_consistency(text)
        self.assertEqual(len(issues), 0)

    def test_mixed_usage(self):
        text = "The frontend is here. The front-end is there."
        issues = self.analyzer.check_consistency(text)
        self.assertTrue(len(issues) > 0)
        self.assertTrue(any(i.preferred == "frontend" for i in issues))

    def test_email_variants(self):
        text = "Send an email to the team. Use e-mail for formal communication."
        issues = self.analyzer.check_consistency(text)
        self.assertTrue(any(i.preferred == "email" for i in issues))


class TestWritingAnalyzerTone(unittest.TestCase):
    def setUp(self):
        self.analyzer = WritingAnalyzer()

    def test_empty_text(self):
        tone = self.analyzer.analyze_tone("")
        self.assertEqual(tone.label, "neutral")

    def test_formal_text(self):
        text = "The system architecture employs distributed consensus protocols."
        tone = self.analyzer.analyze_tone(text)
        self.assertIsInstance(tone, ToneResult)
        self.assertGreaterEqual(tone.formality, 0.0)
        self.assertLessEqual(tone.formality, 1.0)

    def test_informal_text(self):
        text = "Just basically gonna wanna kinda sorta do the stuff and things."
        tone = self.analyzer.analyze_tone(text)
        self.assertLess(tone.formality, 0.5)
        self.assertEqual(tone.label, "informal")

    def test_hedging_text(self):
        text = "Maybe we could possibly perhaps consider this approach, it seems arguably likely."
        tone = self.analyzer.analyze_tone(text)
        self.assertLess(tone.confidence, 0.7)


class TestWritingAnalyzerFull(unittest.TestCase):
    def setUp(self):
        self.analyzer = WritingAnalyzer()

    def test_full_analysis(self):
        text = "We should leverage the API. The frontend and front-end are great."
        result = self.analyzer.analyze(text)
        self.assertIsInstance(result, AnalysisResult)
        self.assertIsInstance(result.readability, ReadabilityScore)
        self.assertIsInstance(result.tone, ToneResult)
        self.assertGreater(result.word_count, 0)
        self.assertGreater(result.sentence_count, 0)
        self.assertTrue(len(result.jargon) > 0)

    def test_analysis_result_defaults(self):
        r = AnalysisResult(
            readability=ReadabilityScore(0, 100, 0, 0),
        )
        self.assertEqual(r.word_count, 0)
        self.assertEqual(r.sentence_count, 0)
        self.assertEqual(len(r.jargon), 0)


if __name__ == "__main__":
    unittest.main()
