"""Tests for DLPPolicyManager."""
from __future__ import annotations

import unittest

from lidco.dlp.policy import DLPPolicy, DLPPolicyManager, PolicyEvaluation


class TestDLPPolicy(unittest.TestCase):
    def test_defaults(self):
        p = DLPPolicy(name="test")
        self.assertEqual(p.rules, [])
        self.assertEqual(p.severity, "high")
        self.assertTrue(p.enabled)


class TestPolicyEvaluation(unittest.TestCase):
    def test_frozen(self):
        e = PolicyEvaluation(policy_name="p", matched=True, severity="high")
        with self.assertRaises(AttributeError):
            e.matched = False  # type: ignore[misc]


class TestDLPPolicyManager(unittest.TestCase):
    def test_add_and_list(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="p1"))
        self.assertEqual(len(mgr.policies()), 1)

    def test_remove(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="p1"))
        self.assertTrue(mgr.remove_policy("p1"))
        self.assertFalse(mgr.remove_policy("p1"))

    def test_enable_disable(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="p1"))
        self.assertTrue(mgr.disable("p1"))
        self.assertEqual(len(mgr.policies(enabled_only=True)), 0)
        self.assertTrue(mgr.enable("p1"))
        self.assertEqual(len(mgr.policies(enabled_only=True)), 1)

    def test_enable_nonexistent(self):
        mgr = DLPPolicyManager()
        self.assertFalse(mgr.enable("nope"))
        self.assertFalse(mgr.disable("nope"))

    def test_evaluate_match(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="no-ssn", rules=[r"\d{3}-\d{2}-\d{4}"], severity="critical"))
        results = mgr.evaluate("SSN: 123-45-6789")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].matched)

    def test_evaluate_no_match(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="no-ssn", rules=[r"\d{3}-\d{2}-\d{4}"]))
        results = mgr.evaluate("nothing sensitive")
        self.assertFalse(results[0].matched)

    def test_evaluate_exception(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="no-email", rules=[r"\S+@\S+"], exceptions=[r"test@"]))
        results = mgr.evaluate("test@example.com")
        self.assertFalse(results[0].matched)
        self.assertTrue(results[0].exception_applied)

    def test_add_exception(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="p1", rules=[r"secret"]))
        self.assertTrue(mgr.add_exception("p1", r"test_secret"))
        self.assertFalse(mgr.add_exception("nope", r"x"))

    def test_summary(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="a"))
        mgr.add_policy(DLPPolicy(name="b", enabled=False))
        s = mgr.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["enabled"], 1)
        self.assertEqual(s["disabled"], 1)

    def test_evaluate_disabled_skipped(self):
        mgr = DLPPolicyManager()
        mgr.add_policy(DLPPolicy(name="off", rules=[r".*"], enabled=False))
        results = mgr.evaluate("anything")
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
