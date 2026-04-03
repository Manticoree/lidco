"""Tests for CascadeRouter (Q245)."""
from __future__ import annotations

import unittest

from lidco.llm.cascade_router import CascadeResult, CascadeRouter, CascadeRule


class TestCascadeRule(unittest.TestCase):
    def test_defaults(self):
        r = CascadeRule(model="gpt-4")
        self.assertEqual(r.model, "gpt-4")
        self.assertEqual(r.timeout, 30.0)
        self.assertEqual(r.fallback_on, ["error", "timeout"])

    def test_custom_timeout(self):
        r = CascadeRule(model="claude", timeout=10.0)
        self.assertEqual(r.timeout, 10.0)

    def test_frozen(self):
        r = CascadeRule(model="x")
        with self.assertRaises(AttributeError):
            r.model = "y"  # type: ignore[misc]


class TestCascadeResult(unittest.TestCase):
    def test_fields(self):
        r = CascadeResult(model_used="a", attempts=[{"m": "a"}], success=True)
        self.assertEqual(r.model_used, "a")
        self.assertTrue(r.success)
        self.assertEqual(len(r.attempts), 1)


class TestCascadeRouterAddRule(unittest.TestCase):
    def test_add_rule(self):
        router = CascadeRouter()
        router.add_rule(CascadeRule(model="a"))
        self.assertEqual(len(router.list_rules()), 1)

    def test_add_multiple_rules(self):
        router = CascadeRouter()
        router.add_rule(CascadeRule(model="a"))
        router.add_rule(CascadeRule(model="b"))
        self.assertEqual(len(router.list_rules()), 2)

    def test_rule_order_preserved(self):
        router = CascadeRouter()
        router.add_rule(CascadeRule(model="first"))
        router.add_rule(CascadeRule(model="second"))
        names = [r.model for r in router.list_rules()]
        self.assertEqual(names, ["first", "second"])


class TestCascadeRouterRoute(unittest.TestCase):
    def test_route_empty_fails(self):
        router = CascadeRouter()
        result = router.route("hello")
        self.assertFalse(result.success)
        self.assertEqual(result.model_used, "")

    def test_route_single_success(self):
        router = CascadeRouter()
        # "abc" has length 3 (odd) -> succeeds
        router.add_rule(CascadeRule(model="abc"))
        result = router.route("test")
        self.assertTrue(result.success)
        self.assertEqual(result.model_used, "abc")

    def test_route_fallback(self):
        router = CascadeRouter()
        # "ab" len 2 (even) -> fails; "abc" len 3 (odd) -> succeeds
        router.add_rule(CascadeRule(model="ab"))
        router.add_rule(CascadeRule(model="abc"))
        result = router.route("test")
        self.assertTrue(result.success)
        self.assertEqual(result.model_used, "abc")
        self.assertEqual(len(result.attempts), 2)

    def test_route_all_fail(self):
        router = CascadeRouter()
        # "ab" and "cd" both even -> fail
        router.add_rule(CascadeRule(model="ab"))
        router.add_rule(CascadeRule(model="cd"))
        result = router.route("test")
        self.assertFalse(result.success)
        self.assertEqual(result.model_used, "cd")

    def test_attempts_contain_request(self):
        router = CascadeRouter()
        router.add_rule(CascadeRule(model="abc"))
        result = router.route("hello world")
        self.assertEqual(result.attempts[0]["request"], "hello world")


class TestCascadeRouterSimulate(unittest.TestCase):
    def test_simulate_empty(self):
        router = CascadeRouter()
        self.assertEqual(router.simulate("x"), [])

    def test_simulate_returns_order(self):
        router = CascadeRouter()
        router.add_rule(CascadeRule(model="a"))
        router.add_rule(CascadeRule(model="b"))
        self.assertEqual(router.simulate("x"), ["a", "b"])


class TestCascadeRouterListRules(unittest.TestCase):
    def test_list_rules_returns_copy(self):
        router = CascadeRouter()
        router.add_rule(CascadeRule(model="a"))
        rules = router.list_rules()
        rules.clear()
        self.assertEqual(len(router.list_rules()), 1)


if __name__ == "__main__":
    unittest.main()
