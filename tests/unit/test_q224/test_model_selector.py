"""Tests for lidco.routing.model_selector."""
from __future__ import annotations

import unittest

from lidco.routing.complexity_estimator import ComplexityResult
from lidco.routing.model_selector import ModelSelection, ModelSelector, RoutingRule


def _result(level: str, score: float = 0.5) -> ComplexityResult:
    return ComplexityResult(level=level, score=score, factors=[], token_estimate=500)


class TestModelSelection(unittest.TestCase):
    def test_frozen(self) -> None:
        s = ModelSelection(model="m", reason="r", complexity="low", fallback_chain=[])
        with self.assertRaises(AttributeError):
            s.model = "x"  # type: ignore[misc]


class TestModelSelector(unittest.TestCase):
    def setUp(self) -> None:
        self.selector = ModelSelector()

    def test_low_selects_haiku(self) -> None:
        sel = self.selector.select(_result("low", 0.1))
        self.assertEqual(sel.model, "claude-haiku-4-5")
        self.assertEqual(sel.complexity, "low")

    def test_medium_selects_sonnet(self) -> None:
        sel = self.selector.select(_result("medium", 0.4))
        self.assertEqual(sel.model, "claude-sonnet-4")

    def test_expert_selects_opus(self) -> None:
        sel = self.selector.select(_result("expert", 0.9))
        self.assertEqual(sel.model, "claude-opus-4")

    def test_fallback_chain_populated(self) -> None:
        sel = self.selector.select(_result("expert"))
        self.assertIn("claude-sonnet-4", sel.fallback_chain)

    def test_add_rule(self) -> None:
        self.selector.add_rule(RoutingRule("low", "medium", "custom-model"))
        self.assertEqual(len(self.selector.rules), 5)

    def test_rules_property_returns_copy(self) -> None:
        rules = self.selector.rules
        rules.append(RoutingRule("low", "low", "x"))
        self.assertNotEqual(len(rules), len(self.selector.rules))

    def test_budget_filters_rules(self) -> None:
        selector = ModelSelector(rules=[
            RoutingRule("low", "expert", "expensive-model", max_cost=0.01),
            RoutingRule("low", "expert", "cheap-model", max_cost=100.0),
        ])
        sel = selector.select(_result("medium"), budget=0.05)
        self.assertEqual(sel.model, "cheap-model")

    def test_no_matching_rule_uses_fallback(self) -> None:
        selector = ModelSelector(rules=[], fallback="fallback-model")
        sel = selector.select(_result("high"))
        self.assertEqual(sel.model, "fallback-model")
        self.assertIn("fallback", sel.reason)

    def test_custom_fallback(self) -> None:
        selector = ModelSelector(fallback="my-model")
        sel = selector.select(_result("low"))
        # default rules still match low -> haiku
        self.assertEqual(sel.model, "claude-haiku-4-5")

    def test_reason_contains_complexity(self) -> None:
        sel = self.selector.select(_result("high"))
        self.assertIn("high", sel.reason)


if __name__ == "__main__":
    unittest.main()
