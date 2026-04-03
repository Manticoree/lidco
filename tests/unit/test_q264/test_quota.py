"""Tests for QuotaEnforcer (Q264)."""
from __future__ import annotations

import unittest

from lidco.tenant.quota import Quota, QuotaResult, QuotaEnforcer


class TestQuotaDataclass(unittest.TestCase):
    def test_defaults(self):
        q = Quota(tenant_id="t1", resource="tokens", soft_limit=100, hard_limit=200)
        self.assertEqual(q.current_usage, 0.0)

    def test_fields(self):
        q = Quota(tenant_id="t1", resource="cost", soft_limit=50, hard_limit=100, current_usage=25)
        self.assertEqual(q.current_usage, 25)


class TestQuotaResult(unittest.TestCase):
    def test_frozen(self):
        r = QuotaResult(allowed=True, resource="tokens", usage=0, limit=100)
        with self.assertRaises(AttributeError):
            r.allowed = False  # type: ignore[misc]

    def test_overage_default(self):
        r = QuotaResult(allowed=True, resource="tokens", usage=0, limit=100)
        self.assertEqual(r.overage, 0.0)


class TestSetQuota(unittest.TestCase):
    def test_set_new(self):
        e = QuotaEnforcer()
        q = e.set_quota("t1", "tokens", 80, 100)
        self.assertEqual(q.soft_limit, 80)
        self.assertEqual(q.hard_limit, 100)

    def test_set_updates_existing(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        q = e.set_quota("t1", "tokens", 90, 120)
        self.assertEqual(q.soft_limit, 90)
        self.assertEqual(q.hard_limit, 120)


class TestCheckAndConsume(unittest.TestCase):
    def test_check_within_limit(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        r = e.check("t1", "tokens", 50)
        self.assertTrue(r.allowed)
        self.assertEqual(r.overage, 0.0)

    def test_check_over_hard(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        r = e.check("t1", "tokens", 150)
        self.assertFalse(r.allowed)
        self.assertGreater(r.overage, 0)

    def test_check_no_quota(self):
        e = QuotaEnforcer()
        r = e.check("t1", "tokens", 999)
        self.assertTrue(r.allowed)

    def test_consume_updates_usage(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        r = e.consume("t1", "tokens", 50)
        self.assertTrue(r.allowed)
        self.assertEqual(r.usage, 50)

    def test_consume_exceeds_hard(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        e.consume("t1", "tokens", 60)
        r = e.consume("t1", "tokens", 60)
        self.assertFalse(r.allowed)
        self.assertEqual(r.usage, 120)

    def test_consume_no_quota(self):
        e = QuotaEnforcer()
        r = e.consume("t1", "tokens", 50)
        self.assertTrue(r.allowed)


class TestResetAndLimits(unittest.TestCase):
    def test_reset_specific(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        e.consume("t1", "tokens", 50)
        count = e.reset("t1", "tokens")
        self.assertEqual(count, 1)
        self.assertEqual(e.get_usage("t1", "tokens").current_usage, 0.0)

    def test_reset_all(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        e.set_quota("t1", "cost", 10, 20)
        e.consume("t1", "tokens", 50)
        e.consume("t1", "cost", 5)
        count = e.reset("t1")
        self.assertEqual(count, 2)

    def test_over_soft_limit(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        e.consume("t1", "tokens", 90)
        self.assertEqual(len(e.over_soft_limit()), 1)

    def test_over_hard_limit(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        e.consume("t1", "tokens", 110)
        self.assertEqual(len(e.over_hard_limit()), 1)

    def test_get_usage_missing(self):
        e = QuotaEnforcer()
        self.assertIsNone(e.get_usage("t1", "tokens"))

    def test_all_quotas_filtered(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        e.set_quota("t2", "tokens", 80, 100)
        self.assertEqual(len(e.all_quotas("t1")), 1)
        self.assertEqual(len(e.all_quotas()), 2)

    def test_summary(self):
        e = QuotaEnforcer()
        e.set_quota("t1", "tokens", 80, 100)
        s = e.summary()
        self.assertEqual(s["total_quotas"], 1)


if __name__ == "__main__":
    unittest.main()
