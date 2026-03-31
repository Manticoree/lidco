"""Tests for AlertRuleEngine (Task 869)."""
from __future__ import annotations

import unittest

from lidco.alerts.alert_rule import AlertRuleEngine, Rule


class TestRule(unittest.TestCase):
    def test_dataclass_fields(self):
        r = Rule(name="r1", condition_fn=lambda ctx: True, action="notify", message_template="hi")
        self.assertEqual(r.name, "r1")
        self.assertTrue(r.enabled)

    def test_disabled_rule(self):
        r = Rule(name="r2", condition_fn=lambda ctx: True, action="warn", message_template="x", enabled=False)
        self.assertFalse(r.enabled)


class TestAlertRuleEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AlertRuleEngine()

    def test_add_rule(self):
        r = self.engine.add_rule("r1", lambda ctx: True, "notify", "hello")
        self.assertIsInstance(r, Rule)
        self.assertEqual(r.name, "r1")

    def test_add_rule_invalid_action(self):
        with self.assertRaises(ValueError):
            self.engine.add_rule("r1", lambda ctx: True, "explode", "msg")

    def test_remove_rule(self):
        self.engine.add_rule("r1", lambda ctx: True, "notify", "msg")
        self.assertTrue(self.engine.remove_rule("r1"))
        self.assertEqual(len(self.engine.list_rules()), 0)

    def test_remove_nonexistent(self):
        self.assertFalse(self.engine.remove_rule("nope"))

    def test_enable_disable(self):
        self.engine.add_rule("r1", lambda ctx: True, "notify", "msg")
        self.engine.disable("r1")
        self.assertFalse(self.engine.list_rules()[0].enabled)
        self.engine.enable("r1")
        self.assertTrue(self.engine.list_rules()[0].enabled)

    def test_evaluate_triggered(self):
        self.engine.add_rule("r1", lambda ctx: ctx.get("x", 0) > 10, "warn", "x is {x}")
        results = self.engine.evaluate({"x": 20})
        self.assertEqual(len(results), 1)
        rule, msg = results[0]
        self.assertEqual(rule.name, "r1")
        self.assertEqual(msg, "x is 20")

    def test_evaluate_not_triggered(self):
        self.engine.add_rule("r1", lambda ctx: ctx.get("x", 0) > 10, "warn", "x is {x}")
        results = self.engine.evaluate({"x": 5})
        self.assertEqual(len(results), 0)

    def test_evaluate_skips_disabled(self):
        self.engine.add_rule("r1", lambda ctx: True, "notify", "msg")
        self.engine.disable("r1")
        results = self.engine.evaluate({})
        self.assertEqual(len(results), 0)

    def test_evaluate_multiple_rules(self):
        self.engine.add_rule("r1", lambda ctx: True, "notify", "one")
        self.engine.add_rule("r2", lambda ctx: True, "warn", "two")
        results = self.engine.evaluate({})
        self.assertEqual(len(results), 2)

    def test_evaluate_condition_exception(self):
        self.engine.add_rule("r1", lambda ctx: 1 / 0, "notify", "msg")
        results = self.engine.evaluate({})
        self.assertEqual(len(results), 0)

    def test_evaluate_template_exception(self):
        self.engine.add_rule("r1", lambda ctx: True, "notify", "{missing_key}")
        results = self.engine.evaluate({})
        self.assertEqual(len(results), 0)

    def test_list_rules_empty(self):
        self.assertEqual(self.engine.list_rules(), [])

    def test_list_rules_populated(self):
        self.engine.add_rule("a", lambda ctx: True, "notify", "m")
        self.engine.add_rule("b", lambda ctx: True, "warn", "m")
        self.assertEqual(len(self.engine.list_rules()), 2)

    def test_triggered_count_zero(self):
        self.assertEqual(self.engine.triggered_count("nope"), 0)

    def test_triggered_count_increments(self):
        self.engine.add_rule("r1", lambda ctx: True, "notify", "msg")
        self.engine.evaluate({})
        self.engine.evaluate({})
        self.assertEqual(self.engine.triggered_count("r1"), 2)

    def test_triggered_count_not_triggered(self):
        self.engine.add_rule("r1", lambda ctx: False, "notify", "msg")
        self.engine.evaluate({})
        self.assertEqual(self.engine.triggered_count("r1"), 0)

    def test_add_rule_replaces(self):
        self.engine.add_rule("r1", lambda ctx: True, "notify", "old")
        self.engine.add_rule("r1", lambda ctx: True, "warn", "new")
        rules = self.engine.list_rules()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].action, "warn")

    def test_valid_actions(self):
        for action in ("notify", "warn", "block"):
            r = self.engine.add_rule(f"r_{action}", lambda ctx: True, action, "msg")
            self.assertEqual(r.action, action)

    def test_enable_nonexistent_no_error(self):
        self.engine.enable("nope")  # should not raise

    def test_disable_nonexistent_no_error(self):
        self.engine.disable("nope")  # should not raise


if __name__ == "__main__":
    unittest.main()
