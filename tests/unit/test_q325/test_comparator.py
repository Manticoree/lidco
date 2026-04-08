"""Tests for lidco.envmgmt.comparator — EnvComparator."""

from __future__ import annotations

import unittest

from lidco.envmgmt.comparator import (
    ComparisonResult,
    ConfigDiff,
    DiffKind,
    DriftItem,
    EnvComparator,
    SyncRecommendation,
)
from lidco.envmgmt.provisioner import EnvProvisioner, EnvTemplate, EnvTier


def _make_env(name: str, tier: EnvTier, config: dict, resources: dict | None = None, tags: dict | None = None):
    """Helper to provision an env quickly."""
    p = EnvProvisioner()
    tmpl = EnvTemplate(
        name=name,
        tier=tier,
        config=config,
        resources=resources or {},
        tags=tags or {},
    )
    p.register_template(tmpl)
    return p.provision(name)


class TestEnvComparator(unittest.TestCase):
    def setUp(self) -> None:
        self.comparator = EnvComparator()

    def test_identical_envs_no_diffs(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {"port": 80})
        e2 = _make_env("b", EnvTier.DEV, {"port": 80})
        result = self.comparator.compare(e1, e2)
        self.assertFalse(result.has_diffs)
        self.assertEqual(result.drift_count, 0)

    def test_config_changed(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {"port": 80})
        e2 = _make_env("b", EnvTier.DEV, {"port": 9090})
        result = self.comparator.compare(e1, e2)
        self.assertTrue(result.has_diffs)
        port_diffs = [d for d in result.config_diffs if d.key == "port"]
        self.assertEqual(len(port_diffs), 1)
        self.assertEqual(port_diffs[0].kind, DiffKind.CHANGED)

    def test_config_added_key(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {})
        e2 = _make_env("b", EnvTier.DEV, {"extra": True})
        result = self.comparator.compare(e1, e2)
        added = [d for d in result.config_diffs if d.kind == DiffKind.ADDED]
        self.assertTrue(len(added) >= 1)

    def test_config_removed_key(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {"old_key": 1})
        e2 = _make_env("b", EnvTier.DEV, {})
        result = self.comparator.compare(e1, e2)
        removed = [d for d in result.config_diffs if d.kind == DiffKind.REMOVED]
        self.assertTrue(len(removed) >= 1)

    def test_resource_diff(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {}, resources={"cpu": "2"})
        e2 = _make_env("b", EnvTier.DEV, {}, resources={"cpu": "4"})
        result = self.comparator.compare(e1, e2)
        self.assertTrue(len(result.resource_diffs) >= 1)

    def test_tag_diff(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {}, tags={"team": "alpha"})
        e2 = _make_env("b", EnvTier.DEV, {}, tags={"team": "beta"})
        result = self.comparator.compare(e1, e2)
        self.assertTrue(len(result.tag_diffs) >= 1)

    def test_drift_detection_high_severity(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {"replicas": 1})
        e2 = _make_env("b", EnvTier.DEV, {"replicas": 5})
        result = self.comparator.compare(e1, e2)
        high = [d for d in result.drift_items if d.severity == "high"]
        self.assertTrue(len(high) >= 1)

    def test_drift_detection_medium_severity(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {"custom_key": "x"})
        e2 = _make_env("b", EnvTier.DEV, {"custom_key": "y"})
        result = self.comparator.compare(e1, e2)
        medium = [d for d in result.drift_items if d.severity == "medium"]
        self.assertTrue(len(medium) >= 1)

    def test_sync_recommendations_update(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {"port": 80})
        e2 = _make_env("b", EnvTier.DEV, {"port": 9090})
        result = self.comparator.compare(e1, e2)
        updates = [r for r in result.recommendations if r.action == "update"]
        self.assertTrue(len(updates) >= 1)

    def test_sync_recommendations_add(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {})
        e2 = _make_env("b", EnvTier.DEV, {"new_key": 42})
        result = self.comparator.compare(e1, e2)
        adds = [r for r in result.recommendations if r.action == "add"]
        self.assertTrue(len(adds) >= 1)

    def test_sync_recommendations_remove(self) -> None:
        e1 = _make_env("a", EnvTier.DEV, {"gone": True})
        e2 = _make_env("b", EnvTier.DEV, {})
        result = self.comparator.compare(e1, e2)
        removes = [r for r in result.recommendations if r.action == "remove"]
        self.assertTrue(len(removes) >= 1)

    def test_comparison_result_names(self) -> None:
        e1 = _make_env("left", EnvTier.DEV, {})
        e2 = _make_env("right", EnvTier.DEV, {})
        result = self.comparator.compare(e1, e2)
        self.assertEqual(result.left_name, e1.name)
        self.assertEqual(result.right_name, e2.name)

    def test_no_drift_when_identical(self) -> None:
        e1 = _make_env("a", EnvTier.STAGING, {"port": 80})
        e2 = _make_env("b", EnvTier.STAGING, {"port": 80})
        result = self.comparator.compare(e1, e2)
        self.assertEqual(result.drift_count, 0)


class TestDataclasses(unittest.TestCase):
    def test_config_diff_frozen(self) -> None:
        d = ConfigDiff(key="k", kind=DiffKind.CHANGED, left_value=1, right_value=2)
        self.assertEqual(d.key, "k")

    def test_drift_item_defaults(self) -> None:
        d = DriftItem(key="x", expected=1, actual=2)
        self.assertEqual(d.severity, "medium")

    def test_sync_recommendation(self) -> None:
        r = SyncRecommendation(action="update", key="k", value=1, reason="test")
        self.assertEqual(r.action, "update")

    def test_diff_kind_values(self) -> None:
        self.assertEqual(DiffKind.ADDED.value, "added")
        self.assertEqual(DiffKind.REMOVED.value, "removed")
        self.assertEqual(DiffKind.CHANGED.value, "changed")


if __name__ == "__main__":
    unittest.main()
