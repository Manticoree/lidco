"""Tests for PolicyEnforcer."""
from __future__ import annotations

import unittest

from lidco.enterprise.policy_enforcer import (
    Policy,
    PolicyAction,
    PolicyEnforcer,
    PolicyViolation,
)


class TestPolicyAction(unittest.TestCase):
    def test_values(self):
        self.assertEqual(PolicyAction.ALLOW.value, "allow")
        self.assertEqual(PolicyAction.DENY.value, "deny")
        self.assertEqual(PolicyAction.WARN.value, "warn")
        self.assertEqual(PolicyAction.AUDIT.value, "audit")


class TestPolicyFrozen(unittest.TestCase):
    def test_frozen(self):
        p = Policy(name="p1", resource="res", action=PolicyAction.DENY)
        with self.assertRaises(AttributeError):
            p.name = "other"  # type: ignore[misc]


class TestAddRemovePolicy(unittest.TestCase):
    def test_add_and_list(self):
        e = PolicyEnforcer()
        p = Policy(name="p1", resource="tool.*", action=PolicyAction.DENY)
        e.add_policy(p)
        self.assertEqual(len(e.list_policies()), 1)
        self.assertEqual(e.list_policies()[0].name, "p1")

    def test_remove_existing(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="p1", resource="x", action=PolicyAction.ALLOW))
        self.assertTrue(e.remove_policy("p1"))
        self.assertEqual(len(e.list_policies()), 0)

    def test_remove_nonexistent(self):
        e = PolicyEnforcer()
        self.assertFalse(e.remove_policy("nope"))


class TestCheck(unittest.TestCase):
    def test_allow_when_no_policies(self):
        e = PolicyEnforcer()
        self.assertEqual(e.check("anything"), PolicyAction.ALLOW)

    def test_deny_matching(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="block", resource="secret", action=PolicyAction.DENY, reason="forbidden"))
        self.assertEqual(e.check("secret"), PolicyAction.DENY)

    def test_allow_non_matching(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="block", resource="secret", action=PolicyAction.DENY))
        self.assertEqual(e.check("public"), PolicyAction.ALLOW)

    def test_wildcard_matching(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="all", resource="*", action=PolicyAction.WARN))
        self.assertEqual(e.check("anything"), PolicyAction.WARN)

    def test_prefix_wildcard(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="tools", resource="tool.*", action=PolicyAction.AUDIT))
        self.assertEqual(e.check("tool.shell"), PolicyAction.AUDIT)
        self.assertEqual(e.check("other"), PolicyAction.ALLOW)

    def test_priority_highest_wins(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="low", resource="res", action=PolicyAction.WARN, priority=1))
        e.add_policy(Policy(name="high", resource="res", action=PolicyAction.DENY, priority=10))
        self.assertEqual(e.check("res"), PolicyAction.DENY)


class TestViolations(unittest.TestCase):
    def test_violations_recorded(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="block", resource="x", action=PolicyAction.DENY, reason="no"))
        e.check("x")
        vs = e.violations()
        self.assertEqual(len(vs), 1)
        self.assertEqual(vs[0].policy_name, "block")
        self.assertEqual(vs[0].action, PolicyAction.DENY)

    def test_clear_violations(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="block", resource="x", action=PolicyAction.DENY))
        e.check("x")
        count = e.clear_violations()
        self.assertEqual(count, 1)
        self.assertEqual(len(e.violations()), 0)

    def test_no_violation_for_allow(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="ok", resource="x", action=PolicyAction.ALLOW))
        e.check("x")
        self.assertEqual(len(e.violations()), 0)


class TestCheckWithViolations(unittest.TestCase):
    def test_returns_tuple(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="warn", resource="x", action=PolicyAction.WARN, reason="careful"))
        action, vs = e.check_with_violations("x")
        self.assertEqual(action, PolicyAction.WARN)
        self.assertEqual(len(vs), 1)


class TestSummary(unittest.TestCase):
    def test_summary_content(self):
        e = PolicyEnforcer()
        e.add_policy(Policy(name="p1", resource="r", action=PolicyAction.DENY))
        s = e.summary()
        self.assertIn("1 policies", s)
        self.assertIn("p1", s)


if __name__ == "__main__":
    unittest.main()
