"""Tests for lidco.enterprise.distributor."""
from __future__ import annotations

import unittest

from lidco.enterprise.distributor import ConfigDistributor, ConfigVersion, RolloutStatus


class TestConfigVersion(unittest.TestCase):
    def test_frozen(self) -> None:
        cv = ConfigVersion(version=1, config={"a": 1}, created_at=0.0)
        with self.assertRaises(AttributeError):
            cv.version = 2  # type: ignore[misc]

    def test_defaults(self) -> None:
        cv = ConfigVersion(version=1, config={}, created_at=0.0)
        self.assertEqual(cv.author, "system")
        self.assertEqual(cv.description, "")


class TestConfigDistributor(unittest.TestCase):
    def setUp(self) -> None:
        self.cd = ConfigDistributor()

    def test_publish_increments_version(self) -> None:
        v1 = self.cd.publish({"a": 1})
        v2 = self.cd.publish({"b": 2})
        self.assertEqual(v1.version, 1)
        self.assertEqual(v2.version, 2)

    def test_versions_list(self) -> None:
        self.cd.publish({"x": 1})
        self.cd.publish({"y": 2})
        self.assertEqual(len(self.cd.versions()), 2)

    def test_get_version(self) -> None:
        self.cd.publish({"a": 1}, author="alice")
        v = self.cd.get_version(1)
        self.assertIsNotNone(v)
        self.assertEqual(v.author, "alice")  # type: ignore[union-attr]

    def test_get_version_missing(self) -> None:
        self.assertIsNone(self.cd.get_version(99))

    def test_diff_added_removed_changed(self) -> None:
        self.cd.publish({"a": 1, "b": 2})
        self.cd.publish({"b": 99, "c": 3})
        d = self.cd.diff(1, 2)
        self.assertIn("a", d["removed"])
        self.assertIn("c", d["added"])
        self.assertIn("b", d["changed"])

    def test_diff_missing_version(self) -> None:
        d = self.cd.diff(1, 2)
        self.assertEqual(d["added"], [])

    def test_rollout_full(self) -> None:
        self.cd.publish({"a": 1})
        status = self.cd.rollout(1, ["t1", "t2", "t3"])
        self.assertEqual(status.applied_count, 3)
        self.assertEqual(status.status, "completed")

    def test_rollout_canary(self) -> None:
        self.cd.publish({"a": 1})
        status = self.cd.rollout(1, ["t1", "t2", "t3", "t4"], canary_pct=50)
        self.assertEqual(status.applied_count, 2)
        self.assertEqual(status.status, "in_progress")

    def test_rollback(self) -> None:
        self.cd.publish({"a": 1})
        self.cd.rollout(1, ["t1"])
        rb = self.cd.rollback(1)
        self.assertIsNotNone(rb)
        self.assertEqual(rb.status, "rolled_back")  # type: ignore[union-attr]

    def test_rollback_missing(self) -> None:
        self.assertIsNone(self.cd.rollback(99))

    def test_current_version(self) -> None:
        self.assertIsNone(self.cd.current_version())
        self.cd.publish({"x": 1})
        self.assertEqual(self.cd.current_version().version, 1)  # type: ignore[union-attr]

    def test_summary(self) -> None:
        self.cd.publish({"a": 1})
        s = self.cd.summary()
        self.assertEqual(s["total_versions"], 1)


if __name__ == "__main__":
    unittest.main()
