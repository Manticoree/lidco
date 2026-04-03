"""Tests for EnsembleRunner (Q245)."""
from __future__ import annotations

import unittest

from lidco.llm.ensemble_runner import EnsembleResult, EnsembleRunner


class TestEnsembleResult(unittest.TestCase):
    def test_fields(self):
        r = EnsembleResult(responses=[{"model": "a", "text": "hi"}], winner="a", method="vote")
        self.assertEqual(r.winner, "a")
        self.assertEqual(r.method, "vote")
        self.assertEqual(len(r.responses), 1)

    def test_frozen(self):
        r = EnsembleResult(responses=[], winner="", method="")
        with self.assertRaises(AttributeError):
            r.winner = "x"  # type: ignore[misc]


class TestEnsembleRunnerAddModel(unittest.TestCase):
    def test_add_model(self):
        runner = EnsembleRunner()
        runner.add_model("gpt-4")
        self.assertEqual(len(runner.list_models()), 1)

    def test_add_model_with_weight(self):
        runner = EnsembleRunner()
        runner.add_model("gpt-4", weight=2.0)
        models = runner.list_models()
        self.assertEqual(models[0]["weight"], 2.0)

    def test_default_weight(self):
        runner = EnsembleRunner()
        runner.add_model("m")
        self.assertEqual(runner.list_models()[0]["weight"], 1.0)

    def test_add_multiple(self):
        runner = EnsembleRunner()
        runner.add_model("a")
        runner.add_model("b")
        runner.add_model("c")
        self.assertEqual(len(runner.list_models()), 3)


class TestEnsembleRunnerRun(unittest.TestCase):
    def test_run_returns_result(self):
        runner = EnsembleRunner()
        runner.add_model("a")
        result = runner.run("prompt")
        self.assertIsInstance(result, EnsembleResult)
        self.assertEqual(result.method, "vote")

    def test_run_responses_format(self):
        runner = EnsembleRunner()
        runner.add_model("gpt-4")
        result = runner.run("hello")
        self.assertEqual(len(result.responses), 1)
        self.assertEqual(result.responses[0]["model"], "gpt-4")
        self.assertEqual(result.responses[0]["text"], "Response from gpt-4")

    def test_run_multiple_models(self):
        runner = EnsembleRunner()
        runner.add_model("a")
        runner.add_model("b")
        result = runner.run("test")
        self.assertEqual(len(result.responses), 2)

    def test_run_empty_ensemble(self):
        runner = EnsembleRunner()
        result = runner.run("test")
        self.assertEqual(len(result.responses), 0)


class TestEnsembleRunnerVote(unittest.TestCase):
    def test_vote_majority(self):
        runner = EnsembleRunner()
        responses = [
            {"model": "a", "text": "yes"},
            {"model": "b", "text": "yes"},
            {"model": "c", "text": "no"},
        ]
        winner = runner.vote(responses)
        self.assertEqual(winner, "a")  # first model with majority text

    def test_vote_tie_first_wins(self):
        runner = EnsembleRunner()
        responses = [
            {"model": "a", "text": "x"},
            {"model": "b", "text": "y"},
        ]
        winner = runner.vote(responses)
        self.assertIn(winner, ("a", "b"))

    def test_vote_empty(self):
        runner = EnsembleRunner()
        self.assertEqual(runner.vote([]), "")

    def test_vote_single(self):
        runner = EnsembleRunner()
        winner = runner.vote([{"model": "solo", "text": "hello"}])
        self.assertEqual(winner, "solo")


class TestEnsembleRunnerMerge(unittest.TestCase):
    def test_merge_unique(self):
        runner = EnsembleRunner()
        responses = [
            {"model": "a", "text": "hello"},
            {"model": "b", "text": "world"},
        ]
        merged = runner.merge(responses)
        self.assertEqual(merged, "hello\nworld")

    def test_merge_deduplicates(self):
        runner = EnsembleRunner()
        responses = [
            {"model": "a", "text": "same"},
            {"model": "b", "text": "same"},
        ]
        merged = runner.merge(responses)
        self.assertEqual(merged, "same")

    def test_merge_empty(self):
        runner = EnsembleRunner()
        self.assertEqual(runner.merge([]), "")


if __name__ == "__main__":
    unittest.main()
