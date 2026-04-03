"""Tests for lidco.routing.complexity_estimator."""
from __future__ import annotations

import unittest

from lidco.routing.complexity_estimator import ComplexityEstimator, ComplexityResult


class TestComplexityResult(unittest.TestCase):
    def test_frozen(self) -> None:
        r = ComplexityResult(level="low", score=0.1, factors=[], token_estimate=100)
        with self.assertRaises(AttributeError):
            r.level = "high"  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = ComplexityResult(level="low", score=0.0)
        self.assertEqual(r.factors, [])
        self.assertEqual(r.token_estimate, 0)


class TestComplexityEstimator(unittest.TestCase):
    def setUp(self) -> None:
        self.estimator = ComplexityEstimator()

    def test_short_prompt_low(self) -> None:
        result = self.estimator.estimate("Fix typo")
        self.assertEqual(result.level, "low")
        self.assertLess(result.score, 0.25)

    def test_medium_prompt(self) -> None:
        prompt = (
            "Refactor the auth module in src/auth.py to use the new token format, "
            "then update the tests in tests/test_auth.py. After that, also migrate "
            "the session handler to integrate with the distributed cache system."
        )
        result = self.estimator.estimate(prompt)
        self.assertIn(result.level, ("medium", "high"))
        self.assertGreater(result.score, 0.0)

    def test_long_prompt_factor(self) -> None:
        prompt = "word " * 150
        result = self.estimator.estimate(prompt)
        self.assertIn("long_prompt", result.factors)

    def test_code_blocks_factor(self) -> None:
        prompt = "Here:\n```python\nprint(1)\n```\nand:\n```js\nconsole.log(1)\n```"
        result = self.estimator.estimate(prompt)
        self.assertIn("code_blocks", result.factors)

    def test_file_references_factor(self) -> None:
        prompt = "Edit src/main.py and tests/test_main.py"
        result = self.estimator.estimate(prompt)
        self.assertIn("file_references", result.factors)

    def test_multi_step_factor(self) -> None:
        prompt = "First do X, then do Y, after that do Z"
        result = self.estimator.estimate(prompt)
        self.assertIn("multi_step", result.factors)

    def test_complexity_keywords_factor(self) -> None:
        prompt = "Architect and design a distributed caching system"
        result = self.estimator.estimate(prompt)
        self.assertIn("complexity_keywords", result.factors)

    def test_tool_hints_increase_score(self) -> None:
        base = self.estimator.estimate("Fix bug")
        with_hints = self.estimator.estimate("Fix bug", tool_hints=["grep", "read", "edit"])
        self.assertGreaterEqual(with_hints.score, base.score)
        self.assertIn("tool_hints", with_hints.factors)

    def test_custom_thresholds(self) -> None:
        est = ComplexityEstimator(thresholds={"low": 0.1, "medium": 0.2, "high": 0.3})
        result = est.estimate("Refactor the module then optimise performance")
        # with lower thresholds more likely to be expert
        self.assertIn(result.level, ("high", "expert"))

    def test_token_estimate_positive(self) -> None:
        result = self.estimator.estimate("Do something")
        self.assertGreater(result.token_estimate, 0)

    def test_score_capped_at_one(self) -> None:
        prompt = ("Refactor and optimise then migrate the distributed security system. " * 20 +
                  "```code```" * 10)
        result = self.estimator.estimate(prompt, tool_hints=["a"] * 30)
        self.assertLessEqual(result.score, 1.0)


if __name__ == "__main__":
    unittest.main()
