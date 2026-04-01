"""Tests for ConversationAnalyzer (Task 1049)."""
from __future__ import annotations

import unittest

from lidco.hookify.analyzer import ConversationAnalyzer, PatternMatch, SuggestedRule
from lidco.hookify.rule import ActionType, EventType


class TestPatternMatch(unittest.TestCase):
    def test_frozen(self):
        pm = PatternMatch(pattern="x", frequency=1, examples=("a",), risk_level="LOW")
        with self.assertRaises(AttributeError):
            pm.pattern = "y"  # type: ignore[misc]

    def test_fields(self):
        pm = PatternMatch(pattern="rm", frequency=3, examples=("rm -rf",), risk_level="HIGH")
        self.assertEqual(pm.pattern, "rm")
        self.assertEqual(pm.frequency, 3)
        self.assertEqual(pm.risk_level, "HIGH")


class TestSuggestedRule(unittest.TestCase):
    def test_frozen(self):
        sr = SuggestedRule(name="n", event_type=EventType.BASH, pattern="p",
                           action=ActionType.WARN, message="m", confidence=0.5)
        with self.assertRaises(AttributeError):
            sr.name = "x"  # type: ignore[misc]

    def test_fields(self):
        sr = SuggestedRule(name="guard", event_type=EventType.FILE, pattern=r"\.env",
                           action=ActionType.WARN, message="warn", confidence=0.7)
        self.assertEqual(sr.confidence, 0.7)
        self.assertEqual(sr.event_type, EventType.FILE)


class TestDetectPatterns(unittest.TestCase):
    def setUp(self):
        self.analyzer = ConversationAnalyzer()

    def test_detects_rm_rf(self):
        messages = ["run rm -rf /tmp/junk", "okay"]
        patterns = self.analyzer.detect_patterns(messages)
        self.assertTrue(any("rm" in p.pattern for p in patterns))

    def test_detects_force_push(self):
        messages = ["git push -f origin main"]
        patterns = self.analyzer.detect_patterns(messages)
        self.assertTrue(any("push" in p.pattern for p in patterns))

    def test_detects_env_access(self):
        messages = ["reading .env file"]
        patterns = self.analyzer.detect_patterns(messages)
        self.assertTrue(any("env" in p.pattern for p in patterns))

    def test_detects_eval_exec(self):
        messages = ["eval('dangerous')"]
        patterns = self.analyzer.detect_patterns(messages)
        self.assertTrue(any("eval" in p.pattern for p in patterns))

    def test_no_patterns(self):
        messages = ["hello world", "how are you"]
        patterns = self.analyzer.detect_patterns(messages)
        self.assertEqual(len(patterns), 0)

    def test_frequency_count(self):
        messages = ["rm -rf a", "rm -rf b", "rm -rf c"]
        patterns = self.analyzer.detect_patterns(messages)
        rm_pat = [p for p in patterns if "rm" in p.pattern]
        self.assertEqual(rm_pat[0].frequency, 3)

    def test_examples_capped(self):
        messages = [f"rm -rf item{i}" for i in range(10)]
        patterns = self.analyzer.detect_patterns(messages)
        rm_pat = [p for p in patterns if "rm" in p.pattern]
        self.assertLessEqual(len(rm_pat[0].examples), 5)


class TestSuggestRules(unittest.TestCase):
    def setUp(self):
        self.analyzer = ConversationAnalyzer()

    def test_suggests_from_patterns(self):
        pm = PatternMatch(pattern=r"rm\s+-rf\s+", frequency=2, examples=("rm -rf /",), risk_level="HIGH")
        suggestions = self.analyzer.suggest_rules((pm,))
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].name, "rm_rf_guard")
        self.assertGreater(suggestions[0].confidence, 0.8)

    def test_empty_patterns(self):
        self.assertEqual(self.analyzer.suggest_rules(()), ())

    def test_confidence_capped_at_1(self):
        pm = PatternMatch(pattern=r"rm\s+-rf\s+", frequency=100, examples=(), risk_level="HIGH")
        suggestions = self.analyzer.suggest_rules((pm,))
        self.assertLessEqual(suggestions[0].confidence, 1.0)


class TestAnalyze(unittest.TestCase):
    def test_full_pipeline(self):
        analyzer = ConversationAnalyzer()
        history = [
            {"role": "user", "content": "run rm -rf /tmp"},
            {"role": "assistant", "content": "done"},
        ]
        suggestions = analyzer.analyze(history)
        self.assertGreater(len(suggestions), 0)

    def test_empty_history(self):
        analyzer = ConversationAnalyzer()
        self.assertEqual(analyzer.analyze([]), ())

    def test_non_string_content_skipped(self):
        analyzer = ConversationAnalyzer()
        history = [{"role": "user", "content": 123}]
        self.assertEqual(analyzer.analyze(history), ())


class TestAllExports(unittest.TestCase):
    def test_all_defined(self):
        from lidco.hookify import analyzer
        self.assertIn("ConversationAnalyzer", analyzer.__all__)
        self.assertIn("SuggestedRule", analyzer.__all__)
        self.assertIn("PatternMatch", analyzer.__all__)


if __name__ == "__main__":
    unittest.main()
