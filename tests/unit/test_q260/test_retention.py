"""Tests for lidco.compliance.retention."""
from __future__ import annotations

import unittest

from lidco.compliance.retention import RetentionManager, RetentionPolicy, RetentionRecord


class TestRetentionPolicy(unittest.TestCase):
    def test_fields(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        self.assertEqual(p.name, "logs")
        self.assertEqual(p.retention_days, 30)
        self.assertFalse(p.legal_hold)

    def test_legal_hold_default(self) -> None:
        p = RetentionPolicy(name="x", resource_pattern=".*", retention_days=1, action="archive", legal_hold=True)
        self.assertTrue(p.legal_hold)


class TestRetentionRecord(unittest.TestCase):
    def test_frozen(self) -> None:
        r = RetentionRecord(resource="a.log", policy_name="logs", action="delete", timestamp=1.0)
        with self.assertRaises(AttributeError):
            r.resource = "b.log"  # type: ignore[misc]


class TestRetentionManager(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = RetentionManager()

    def test_add_policy(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        result = self.mgr.add_policy(p)
        self.assertEqual(result.name, "logs")
        self.assertEqual(len(self.mgr.policies()), 1)

    def test_remove_policy(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        self.mgr.add_policy(p)
        self.assertTrue(self.mgr.remove_policy("logs"))
        self.assertFalse(self.mgr.remove_policy("logs"))
        self.assertEqual(len(self.mgr.policies()), 0)

    def test_set_legal_hold(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        self.mgr.add_policy(p)
        result = self.mgr.set_legal_hold("logs", True)
        self.assertIsNotNone(result)
        self.assertTrue(result.legal_hold)

    def test_set_legal_hold_missing(self) -> None:
        self.assertIsNone(self.mgr.set_legal_hold("nope", True))

    def test_evaluate_match(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        self.mgr.add_policy(p)
        record = self.mgr.evaluate("app.log", 45)
        self.assertIsNotNone(record)
        self.assertEqual(record.action, "delete")
        self.assertEqual(record.policy_name, "logs")

    def test_evaluate_not_expired(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        self.mgr.add_policy(p)
        record = self.mgr.evaluate("app.log", 10)
        self.assertIsNone(record)

    def test_evaluate_legal_hold(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete", legal_hold=True)
        self.mgr.add_policy(p)
        record = self.mgr.evaluate("app.log", 45)
        self.assertIsNotNone(record)
        self.assertTrue(record.held)
        self.assertEqual(record.action, "hold")

    def test_pending_actions(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        self.mgr.add_policy(p)
        resources = [("app.log", 45), ("data.csv", 100), ("error.log", 5)]
        results = self.mgr.pending_actions(resources)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].resource, "app.log")

    def test_audit_trail(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="archive")
        self.mgr.add_policy(p)
        self.mgr.evaluate("a.log", 31)
        self.mgr.evaluate("b.log", 40)
        trail = self.mgr.audit_trail()
        self.assertEqual(len(trail), 2)

    def test_summary(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        self.mgr.add_policy(p)
        s = self.mgr.summary()
        self.assertEqual(s["policy_count"], 1)
        self.assertIn("logs", s["policies"])

    def test_evaluate_no_match(self) -> None:
        p = RetentionPolicy(name="logs", resource_pattern=r"\.log$", retention_days=30, action="delete")
        self.mgr.add_policy(p)
        self.assertIsNone(self.mgr.evaluate("data.csv", 100))


if __name__ == "__main__":
    unittest.main()
