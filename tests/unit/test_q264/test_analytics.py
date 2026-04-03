"""Tests for TenantAnalytics (Q264)."""
from __future__ import annotations

import unittest

from lidco.tenant.analytics import UsageStat, TenantAnalytics


class TestUsageStat(unittest.TestCase):
    def test_frozen(self):
        s = UsageStat(tenant_id="t1", resource="tokens", value=100, timestamp=0.0)
        with self.assertRaises(AttributeError):
            s.value = 200  # type: ignore[misc]

    def test_fields(self):
        s = UsageStat(tenant_id="t1", resource="cost", value=5.5, timestamp=1.0)
        self.assertEqual(s.resource, "cost")
        self.assertEqual(s.value, 5.5)


class TestRecord(unittest.TestCase):
    def test_record_returns_stat(self):
        a = TenantAnalytics()
        s = a.record("t1", "tokens", 100)
        self.assertEqual(s.tenant_id, "t1")
        self.assertGreater(s.timestamp, 0)


class TestTotal(unittest.TestCase):
    def test_total_all_resources(self):
        a = TenantAnalytics()
        a.record("t1", "tokens", 100)
        a.record("t1", "tokens", 50)
        a.record("t1", "cost", 5)
        totals = a.total("t1")
        self.assertEqual(totals["tokens"], 150)
        self.assertEqual(totals["cost"], 5)

    def test_total_specific_resource(self):
        a = TenantAnalytics()
        a.record("t1", "tokens", 100)
        a.record("t1", "cost", 5)
        totals = a.total("t1", resource="tokens")
        self.assertIn("tokens", totals)
        self.assertNotIn("cost", totals)

    def test_total_empty(self):
        a = TenantAnalytics()
        self.assertEqual(a.total("t1"), {})


class TestCompare(unittest.TestCase):
    def test_compare_two_tenants(self):
        a = TenantAnalytics()
        a.record("t1", "tokens", 100)
        a.record("t2", "tokens", 200)
        result = a.compare(["t1", "t2"], "tokens")
        self.assertEqual(result["t1"], 100)
        self.assertEqual(result["t2"], 200)


class TestTopConsumers(unittest.TestCase):
    def test_ranking(self):
        a = TenantAnalytics()
        a.record("t1", "tokens", 100)
        a.record("t2", "tokens", 300)
        a.record("t3", "tokens", 200)
        top = a.top_consumers("tokens", limit=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0][0], "t2")

    def test_empty(self):
        a = TenantAnalytics()
        self.assertEqual(a.top_consumers("tokens"), [])


class TestHistory(unittest.TestCase):
    def test_history_all(self):
        a = TenantAnalytics()
        a.record("t1", "tokens", 100)
        a.record("t1", "cost", 5)
        h = a.history("t1")
        self.assertEqual(len(h), 2)

    def test_history_filtered(self):
        a = TenantAnalytics()
        a.record("t1", "tokens", 100)
        a.record("t1", "cost", 5)
        h = a.history("t1", resource="tokens")
        self.assertEqual(len(h), 1)


class TestCostAllocation(unittest.TestCase):
    def test_cost_allocation(self):
        a = TenantAnalytics()
        a.record("t1", "cost", 10)
        a.record("t2", "cost", 20)
        a.record("t1", "tokens", 100)  # not cost
        alloc = a.cost_allocation()
        self.assertEqual(alloc["t1"], 10)
        self.assertEqual(alloc["t2"], 20)


class TestSummary(unittest.TestCase):
    def test_summary(self):
        a = TenantAnalytics()
        a.record("t1", "tokens", 100)
        s = a.summary()
        self.assertEqual(s["total_records"], 1)
        self.assertEqual(s["tenants_tracked"], 1)


if __name__ == "__main__":
    unittest.main()
