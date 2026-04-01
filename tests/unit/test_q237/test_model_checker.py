"""Tests for src/lidco/doctor/model_checker.py."""
from __future__ import annotations

import unittest

from lidco.doctor.model_checker import ModelCheck, ModelChecker, ModelStatus


class TestCheckModel(unittest.TestCase):
    def test_known_model(self):
        result = ModelChecker().check_model("claude-sonnet-4")
        self.assertEqual(result.status, ModelStatus.AVAILABLE)
        self.assertEqual(result.provider, "anthropic")
        self.assertEqual(result.context_window, 200_000)

    def test_unknown_model(self):
        result = ModelChecker().check_model("fake-model-99")
        self.assertEqual(result.status, ModelStatus.UNKNOWN)
        self.assertEqual(result.provider, "unknown")

    def test_gpt4o(self):
        result = ModelChecker().check_model("gpt-4o")
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.context_window, 128_000)

    def test_gemini(self):
        result = ModelChecker().check_model("gemini-2.5-pro")
        self.assertEqual(result.provider, "google")
        self.assertEqual(result.context_window, 1_000_000)


class TestCheckAll(unittest.TestCase):
    def test_returns_all_known(self):
        results = ModelChecker().check_all()
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r.status == ModelStatus.AVAILABLE for r in results))

    def test_all_have_context_window(self):
        results = ModelChecker().check_all()
        self.assertTrue(all(r.context_window > 0 for r in results))


class TestRecommend(unittest.TestCase):
    def test_low_budget(self):
        recs = ModelChecker().recommend("low")
        models = [r.model for r in recs]
        self.assertIn("gpt-4o-mini", models)

    def test_medium_budget(self):
        recs = ModelChecker().recommend("medium")
        models = [r.model for r in recs]
        self.assertIn("claude-sonnet-4", models)
        self.assertIn("gpt-4o", models)

    def test_high_budget(self):
        recs = ModelChecker().recommend("high")
        models = [r.model for r in recs]
        self.assertIn("claude-opus-4", models)

    def test_unknown_budget_defaults_medium(self):
        recs = ModelChecker().recommend("ultra")
        self.assertEqual(len(recs), 2)  # same as medium


class TestSummary(unittest.TestCase):
    def test_summary_content(self):
        results = [
            ModelCheck("m1", "p1", ModelStatus.AVAILABLE, 100, "m1 ok"),
            ModelCheck("m2", "p2", ModelStatus.UNKNOWN, 0, "m2 unknown"),
        ]
        s = ModelChecker().summary(results)
        self.assertIn("[AVAILABLE]", s)
        self.assertIn("[UNKNOWN]", s)
