"""Tests for PolicyEngine (Q259)."""
from __future__ import annotations

import unittest

from lidco.rbac.policy import Policy, PolicyCondition, PolicyEngine


class TestPolicyCondition(unittest.TestCase):
    def test_frozen(self):
        c = PolicyCondition("role", "eq", "admin")
        with self.assertRaises(AttributeError):
            c.attribute = "x"  # type: ignore[misc]


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PolicyEngine()

    def test_default_deny(self):
        result = self.engine.evaluate({"role": "admin"})
        self.assertEqual(result, "deny")

    def test_add_and_list(self):
        p = Policy(name="p1", effect="allow")
        self.engine.add_policy(p)
        self.assertEqual(len(self.engine.policies()), 1)

    def test_remove_policy(self):
        self.engine.add_policy(Policy(name="p1", effect="allow"))
        self.assertTrue(self.engine.remove_policy("p1"))
        self.assertEqual(len(self.engine.policies()), 0)

    def test_remove_nonexistent(self):
        self.assertFalse(self.engine.remove_policy("ghost"))

    def test_evaluate_allow(self):
        self.engine.add_policy(Policy(
            name="admin_allow",
            effect="allow",
            conditions=[PolicyCondition("role", "eq", "admin")],
        ))
        result = self.engine.evaluate({"role": "admin"})
        self.assertEqual(result, "allow")

    def test_evaluate_no_match_deny(self):
        self.engine.add_policy(Policy(
            name="admin_allow",
            effect="allow",
            conditions=[PolicyCondition("role", "eq", "admin")],
        ))
        result = self.engine.evaluate({"role": "viewer"})
        self.assertEqual(result, "deny")

    def test_priority_highest_wins(self):
        self.engine.add_policy(Policy(
            name="low",
            effect="deny",
            conditions=[PolicyCondition("role", "eq", "dev")],
            priority=1,
        ))
        self.engine.add_policy(Policy(
            name="high",
            effect="allow",
            conditions=[PolicyCondition("role", "eq", "dev")],
            priority=10,
        ))
        result = self.engine.evaluate({"role": "dev"})
        self.assertEqual(result, "allow")

    def test_condition_ne(self):
        self.engine.add_policy(Policy(
            name="ne_test",
            effect="allow",
            conditions=[PolicyCondition("role", "ne", "admin")],
        ))
        self.assertEqual(self.engine.evaluate({"role": "dev"}), "allow")
        self.assertEqual(self.engine.evaluate({"role": "admin"}), "deny")

    def test_condition_in(self):
        self.engine.add_policy(Policy(
            name="in_test",
            effect="allow",
            conditions=[PolicyCondition("role", "in", ["admin", "dev"])],
        ))
        self.assertEqual(self.engine.evaluate({"role": "admin"}), "allow")
        self.assertEqual(self.engine.evaluate({"role": "viewer"}), "deny")

    def test_condition_gt_lt(self):
        self.engine.add_policy(Policy(
            name="gt_test",
            effect="allow",
            conditions=[PolicyCondition("level", "gt", 5)],
        ))
        self.assertEqual(self.engine.evaluate({"level": 10}), "allow")
        self.assertEqual(self.engine.evaluate({"level": 3}), "deny")

    def test_cache_works(self):
        self.engine.add_policy(Policy(name="p1", effect="allow"))
        self.engine.evaluate({"x": 1})
        self.assertEqual(self.engine.summary()["cache_entries"], 1)
        # Same context uses cache
        self.engine.evaluate({"x": 1})
        self.assertEqual(self.engine.summary()["cache_entries"], 1)

    def test_clear_cache(self):
        self.engine.add_policy(Policy(name="p1", effect="allow"))
        self.engine.evaluate({"x": 1})
        count = self.engine.clear_cache()
        self.assertEqual(count, 1)
        self.assertEqual(self.engine.summary()["cache_entries"], 0)

    def test_missing_attribute_no_match(self):
        self.engine.add_policy(Policy(
            name="need_role",
            effect="allow",
            conditions=[PolicyCondition("role", "eq", "admin")],
        ))
        self.assertEqual(self.engine.evaluate({}), "deny")

    def test_summary(self):
        self.engine.add_policy(Policy(name="p1", effect="allow"))
        s = self.engine.summary()
        self.assertEqual(s["total_policies"], 1)
        self.assertEqual(s["cache_size"], 256)

    def test_policy_no_conditions_matches_all(self):
        self.engine.add_policy(Policy(name="catch_all", effect="allow"))
        self.assertEqual(self.engine.evaluate({"anything": True}), "allow")


if __name__ == "__main__":
    unittest.main()
