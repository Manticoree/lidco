"""Tests for lidco.notify.rules."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.notify.rules import NotificationRules, NotifyRule, RuleMatch


class TestNotifyRule(unittest.TestCase):
    def test_defaults(self):
        r = NotifyRule(name="r1", event="completion")
        self.assertEqual(r.level, "info")
        self.assertEqual(r.cooldown_seconds, 0.0)
        self.assertTrue(r.enabled)


class TestNotificationRules(unittest.TestCase):
    def test_default_rules(self):
        rules = NotificationRules()
        names = [r.name for r in rules.rules()]
        self.assertIn("default_completion", names)
        self.assertIn("default_error", names)

    def test_add_rule(self):
        rules = NotificationRules()
        rule = rules.add_rule(NotifyRule(name="custom", event="mention"))
        self.assertEqual(rule.name, "custom")
        self.assertEqual(len(rules.rules()), 3)

    def test_remove_rule(self):
        rules = NotificationRules()
        self.assertTrue(rules.remove_rule("default_completion"))
        self.assertFalse(rules.remove_rule("nonexistent"))

    def test_enable_disable(self):
        rules = NotificationRules()
        self.assertTrue(rules.disable("default_completion"))
        r = [r for r in rules.rules() if r.name == "default_completion"][0]
        self.assertFalse(r.enabled)
        self.assertTrue(rules.enable("default_completion"))
        self.assertTrue(r.enabled)

    def test_enable_disable_missing(self):
        rules = NotificationRules()
        self.assertFalse(rules.enable("nope"))
        self.assertFalse(rules.disable("nope"))

    def test_evaluate_match(self):
        rules = NotificationRules()
        m = rules.evaluate("completion")
        self.assertTrue(m.should_notify)
        self.assertEqual(m.rule_name, "default_completion")
        self.assertEqual(m.reason, "matched")

    def test_evaluate_no_match(self):
        rules = NotificationRules()
        m = rules.evaluate("unknown_event")
        self.assertFalse(m.should_notify)
        self.assertEqual(m.reason, "no matching rule")

    def test_evaluate_disabled_rule(self):
        rules = NotificationRules()
        rules.disable("default_completion")
        m = rules.evaluate("completion")
        self.assertFalse(m.should_notify)
        self.assertEqual(m.reason, "rule disabled")

    def test_evaluate_cooldown(self):
        rules = NotificationRules()
        rules.add_rule(NotifyRule(name="cd", event="ping", cooldown_seconds=100.0))
        m1 = rules.evaluate("ping")
        self.assertTrue(m1.should_notify)
        m2 = rules.evaluate("ping")
        self.assertFalse(m2.should_notify)
        self.assertIn("cooldown", m2.reason)

    def test_evaluate_cooldown_expired(self):
        rules = NotificationRules()
        rules.add_rule(NotifyRule(name="cd2", event="pong", cooldown_seconds=0.01))
        rules.evaluate("pong")
        time.sleep(0.02)
        m = rules.evaluate("pong")
        self.assertTrue(m.should_notify)

    def test_summary(self):
        rules = NotificationRules()
        s = rules.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["enabled"], 2)
        self.assertEqual(s["disabled"], 0)


if __name__ == "__main__":
    unittest.main()
