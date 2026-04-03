"""Tests for SuccessPredictor (Q248)."""
from __future__ import annotations

import unittest

from lidco.conversation.success_predictor import Prediction, SuccessPredictor


class TestPrediction(unittest.TestCase):
    def test_dataclass_fields(self):
        p = Prediction(likelihood=0.8, factors=["good"], recommendation="keep going")
        self.assertEqual(p.likelihood, 0.8)
        self.assertEqual(p.factors, ["good"])
        self.assertEqual(p.recommendation, "keep going")

    def test_frozen(self):
        p = Prediction(likelihood=0.5)
        with self.assertRaises(AttributeError):
            p.likelihood = 0.9  # type: ignore[misc]

    def test_defaults(self):
        p = Prediction(likelihood=0.0)
        self.assertEqual(p.factors, [])
        self.assertEqual(p.recommendation, "")


class TestErrorRate(unittest.TestCase):
    def test_no_errors(self):
        msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        self.assertEqual(SuccessPredictor(msgs).error_rate(), 0.0)

    def test_all_errors(self):
        msgs = [{"role": "assistant", "content": ""}, {"role": "assistant", "content": ""}]
        self.assertEqual(SuccessPredictor(msgs).error_rate(), 1.0)

    def test_error_keyword(self):
        msgs = [{"role": "assistant", "content": "Error: failed"}]
        self.assertEqual(SuccessPredictor(msgs).error_rate(), 1.0)

    def test_empty(self):
        self.assertEqual(SuccessPredictor([]).error_rate(), 0.0)

    def test_mixed(self):
        msgs = [
            {"role": "user", "content": "do it"},
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": "done"},
            {"role": "assistant", "content": "Error: oops"},
        ]
        rate = SuccessPredictor(msgs).error_rate()
        self.assertAlmostEqual(rate, 0.5)


class TestToolDiversity(unittest.TestCase):
    def test_no_tools(self):
        msgs = [{"role": "user", "content": "hi"}]
        self.assertEqual(SuccessPredictor(msgs).tool_diversity(), 0.0)

    def test_all_unique(self):
        msgs = [
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "read"}]},
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "write"}]},
        ]
        self.assertEqual(SuccessPredictor(msgs).tool_diversity(), 1.0)

    def test_all_same(self):
        msgs = [
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "read"}]},
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "read"}]},
            {"role": "assistant", "content": "x", "tool_calls": [{"name": "read"}]},
        ]
        div = SuccessPredictor(msgs).tool_diversity()
        self.assertAlmostEqual(div, 1 / 3)

    def test_string_tool_calls(self):
        msgs = [
            {"role": "assistant", "content": "x", "tool_calls": ["read"]},
            {"role": "assistant", "content": "x", "tool_calls": ["write"]},
        ]
        self.assertEqual(SuccessPredictor(msgs).tool_diversity(), 1.0)


class TestConversationHealth(unittest.TestCase):
    def test_keys(self):
        msgs = [{"role": "user", "content": "hi"}]
        health = SuccessPredictor(msgs).conversation_health()
        self.assertIn("length", health)
        self.assertIn("error_rate", health)
        self.assertIn("diversity", health)
        self.assertIn("score", health)

    def test_empty(self):
        health = SuccessPredictor([]).conversation_health()
        self.assertEqual(health["length"], 0)
        self.assertEqual(health["score"], 0.0)

    def test_score_range(self):
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        health = SuccessPredictor(msgs).conversation_health()
        self.assertGreaterEqual(health["score"], 0.0)
        self.assertLessEqual(health["score"], 1.0)


class TestPredict(unittest.TestCase):
    def test_returns_prediction(self):
        msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        pred = SuccessPredictor(msgs).predict()
        self.assertIsInstance(pred, Prediction)
        self.assertGreaterEqual(pred.likelihood, 0.0)
        self.assertLessEqual(pred.likelihood, 1.0)
        self.assertIsInstance(pred.recommendation, str)
        self.assertTrue(len(pred.recommendation) > 0)

    def test_high_error_rate(self):
        msgs = [{"role": "assistant", "content": ""} for _ in range(5)]
        pred = SuccessPredictor(msgs).predict()
        self.assertIn("High error rate", pred.factors)

    def test_short_conversation(self):
        msgs = [{"role": "user", "content": "hi"}]
        pred = SuccessPredictor(msgs).predict()
        self.assertIn("Conversation too short for reliable prediction", pred.factors)

    def test_empty(self):
        pred = SuccessPredictor([]).predict()
        self.assertEqual(pred.likelihood, 0.0)


if __name__ == "__main__":
    unittest.main()
