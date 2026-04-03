"""Tests for SecretInventory (Q262)."""
from __future__ import annotations

import time
import unittest

from lidco.secrets.inventory import SecretEntry, SecretInventory


def _make(name: str = "db-pass", **kw) -> SecretEntry:
    defaults = dict(
        name=name,
        provider="aws",
        created_at=time.time(),
        exposure_risk="low",
    )
    defaults.update(kw)
    return SecretEntry(**defaults)


class TestSecretEntry(unittest.TestCase):
    def test_defaults(self):
        e = SecretEntry(name="x")
        self.assertEqual(e.provider, "unknown")
        self.assertIsNone(e.last_rotated)
        self.assertEqual(e.rotation_interval_days, 90)
        self.assertEqual(e.exposure_risk, "low")
        self.assertEqual(e.tags, [])


class TestAdd(unittest.TestCase):
    def test_add_sets_created_at(self):
        inv = SecretInventory()
        e = SecretEntry(name="k")
        result = inv.add(e)
        self.assertGreater(result.created_at, 0)

    def test_add_preserves_created_at(self):
        inv = SecretInventory()
        e = SecretEntry(name="k", created_at=100.0)
        result = inv.add(e)
        self.assertEqual(result.created_at, 100.0)

    def test_add_overwrite(self):
        inv = SecretInventory()
        inv.add(SecretEntry(name="k", provider="a"))
        inv.add(SecretEntry(name="k", provider="b"))
        self.assertEqual(inv.get("k").provider, "b")


class TestGet(unittest.TestCase):
    def test_get_existing(self):
        inv = SecretInventory()
        inv.add(_make("x"))
        self.assertIsNotNone(inv.get("x"))

    def test_get_missing(self):
        inv = SecretInventory()
        self.assertIsNone(inv.get("missing"))


class TestRemove(unittest.TestCase):
    def test_remove_existing(self):
        inv = SecretInventory()
        inv.add(_make("x"))
        self.assertTrue(inv.remove("x"))
        self.assertIsNone(inv.get("x"))

    def test_remove_missing(self):
        inv = SecretInventory()
        self.assertFalse(inv.remove("nope"))


class TestStale(unittest.TestCase):
    def test_stale_entries(self):
        inv = SecretInventory()
        old = _make("old", created_at=time.time() - 200 * 86400)
        inv.add(old)
        fresh = _make("fresh", created_at=time.time())
        inv.add(fresh)
        stale = inv.stale(threshold_days=90)
        names = [e.name for e in stale]
        self.assertIn("old", names)
        self.assertNotIn("fresh", names)

    def test_stale_with_rotated(self):
        inv = SecretInventory()
        e = _make("rotated_old", created_at=time.time() - 200 * 86400)
        e.last_rotated = time.time() - 200 * 86400
        inv.add(e)
        self.assertEqual(len(inv.stale(90)), 1)


class TestByRisk(unittest.TestCase):
    def test_filter_by_risk(self):
        inv = SecretInventory()
        inv.add(_make("a", exposure_risk="high"))
        inv.add(_make("b", exposure_risk="low"))
        inv.add(_make("c", exposure_risk="high"))
        high = inv.by_risk("high")
        self.assertEqual(len(high), 2)


class TestMarkRotated(unittest.TestCase):
    def test_mark_rotated(self):
        inv = SecretInventory()
        inv.add(_make("k"))
        before = time.time()
        result = inv.mark_rotated("k")
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.last_rotated, before)

    def test_mark_rotated_missing(self):
        inv = SecretInventory()
        self.assertIsNone(inv.mark_rotated("nope"))


class TestAllEntries(unittest.TestCase):
    def test_all(self):
        inv = SecretInventory()
        inv.add(_make("a"))
        inv.add(_make("b"))
        self.assertEqual(len(inv.all_entries()), 2)


class TestSummary(unittest.TestCase):
    def test_summary(self):
        inv = SecretInventory()
        inv.add(_make("a", exposure_risk="high"))
        inv.add(_make("b", exposure_risk="low"))
        s = inv.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["by_risk"]["high"], 1)
        self.assertEqual(s["by_risk"]["low"], 1)


if __name__ == "__main__":
    unittest.main()
