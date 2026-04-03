"""Tests for NetworkPolicy (Q263)."""
from __future__ import annotations

import unittest

from lidco.netsec.policy import NetworkPolicy, PolicyEvaluation, PolicyRule


class TestPolicyRule(unittest.TestCase):
    def test_frozen(self):
        r = PolicyRule(pattern="*.evil.com", effect="deny")
        with self.assertRaises(AttributeError):
            r.pattern = "other"  # type: ignore[misc]

    def test_defaults(self):
        r = PolicyRule(pattern="x")
        self.assertIsNone(r.port)
        self.assertEqual(r.effect, "deny")
        self.assertEqual(r.description, "")


class TestPolicyEvaluation(unittest.TestCase):
    def test_frozen(self):
        ev = PolicyEvaluation(host="a", port=None, allowed=True, matched_rule=None, reason="ok")
        with self.assertRaises(AttributeError):
            ev.allowed = False  # type: ignore[misc]


class TestDefaultAction(unittest.TestCase):
    def test_default_allow(self):
        policy = NetworkPolicy(default_action="allow")
        ev = policy.evaluate("example.com")
        self.assertTrue(ev.allowed)
        self.assertIsNone(ev.matched_rule)

    def test_default_deny(self):
        policy = NetworkPolicy(default_action="deny")
        ev = policy.evaluate("example.com")
        self.assertFalse(ev.allowed)

    def test_invalid_default(self):
        with self.assertRaises(ValueError):
            NetworkPolicy(default_action="maybe")


class TestRuleMatching(unittest.TestCase):
    def test_deny_rule(self):
        policy = NetworkPolicy()
        policy.add_rule(PolicyRule(pattern="evil.com", effect="deny"))
        ev = policy.evaluate("evil.com")
        self.assertFalse(ev.allowed)
        self.assertEqual(ev.matched_rule, "evil.com")

    def test_allow_rule(self):
        policy = NetworkPolicy(default_action="deny")
        policy.add_rule(PolicyRule(pattern="good.com", effect="allow"))
        ev = policy.evaluate("good.com")
        self.assertTrue(ev.allowed)

    def test_glob_pattern(self):
        policy = NetworkPolicy()
        policy.add_rule(PolicyRule(pattern="*.evil.com", effect="deny"))
        ev = policy.evaluate("sub.evil.com")
        self.assertFalse(ev.allowed)

    def test_first_match_wins(self):
        policy = NetworkPolicy()
        policy.add_rule(PolicyRule(pattern="api.example.com", effect="allow"))
        policy.add_rule(PolicyRule(pattern="example.com", effect="deny"))
        ev = policy.evaluate("api.example.com")
        self.assertTrue(ev.allowed)

    def test_port_matching(self):
        policy = NetworkPolicy()
        policy.add_rule(PolicyRule(pattern="db.internal", port=5432, effect="deny"))
        ev443 = policy.evaluate("db.internal", port=443)
        self.assertTrue(ev443.allowed)  # port doesn't match rule, falls to default
        ev5432 = policy.evaluate("db.internal", port=5432)
        self.assertFalse(ev5432.allowed)


class TestRuleManagement(unittest.TestCase):
    def test_add_and_list(self):
        policy = NetworkPolicy()
        policy.add_rule(PolicyRule(pattern="a.com", effect="deny"))
        policy.add_rule(PolicyRule(pattern="b.com", effect="allow"))
        self.assertEqual(len(policy.rules()), 2)

    def test_remove_rule(self):
        policy = NetworkPolicy()
        policy.add_rule(PolicyRule(pattern="a.com", effect="deny"))
        self.assertTrue(policy.remove_rule("a.com"))
        self.assertEqual(len(policy.rules()), 0)

    def test_remove_nonexistent(self):
        policy = NetworkPolicy()
        self.assertFalse(policy.remove_rule("nope"))


class TestLog(unittest.TestCase):
    def test_log_records_evaluations(self):
        policy = NetworkPolicy()
        policy.evaluate("a.com")
        policy.evaluate("b.com")
        self.assertEqual(len(policy.log()), 2)

    def test_clear_log(self):
        policy = NetworkPolicy()
        policy.evaluate("a.com")
        count = policy.clear_log()
        self.assertEqual(count, 1)
        self.assertEqual(len(policy.log()), 0)


class TestSummary(unittest.TestCase):
    def test_summary(self):
        policy = NetworkPolicy()
        policy.add_rule(PolicyRule(pattern="evil.com", effect="deny"))
        policy.evaluate("good.com")
        policy.evaluate("evil.com")
        s = policy.summary()
        self.assertEqual(s["rules"], 1)
        self.assertEqual(s["evaluations"], 2)
        self.assertEqual(s["allowed"], 1)
        self.assertEqual(s["denied"], 1)
        self.assertEqual(s["default_action"], "allow")


if __name__ == "__main__":
    unittest.main()
