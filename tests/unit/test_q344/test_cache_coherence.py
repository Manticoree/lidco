"""Tests for CacheCoherenceChecker (Q344)."""
from __future__ import annotations

import time
import unittest


def _checker():
    from lidco.stability.cache_coherence import CacheCoherenceChecker
    return CacheCoherenceChecker()


class TestCheckConsistency(unittest.TestCase):
    def test_identical_dicts_are_consistent(self):
        data = {"a": 1, "b": 2}
        result = _checker().check_consistency(data, data)
        self.assertTrue(result["consistent"])
        self.assertEqual(result["stale_keys"], [])
        self.assertEqual(result["missing_keys"], [])
        self.assertEqual(result["extra_keys"], [])

    def test_stale_key_detected(self):
        cache = {"a": 1, "b": 99}
        source = {"a": 1, "b": 2}
        result = _checker().check_consistency(cache, source)
        self.assertFalse(result["consistent"])
        self.assertIn("b", result["stale_keys"])

    def test_missing_key_detected(self):
        cache = {"a": 1}
        source = {"a": 1, "b": 2}
        result = _checker().check_consistency(cache, source)
        self.assertFalse(result["consistent"])
        self.assertIn("b", result["missing_keys"])

    def test_extra_key_detected(self):
        cache = {"a": 1, "extra": 99}
        source = {"a": 1}
        result = _checker().check_consistency(cache, source)
        self.assertFalse(result["consistent"])
        self.assertIn("extra", result["extra_keys"])

    def test_empty_cache_and_source_are_consistent(self):
        result = _checker().check_consistency({}, {})
        self.assertTrue(result["consistent"])

    def test_all_issues_combined(self):
        cache = {"a": 1, "b": 99, "c": 3}
        source = {"a": 1, "b": 2, "d": 4}
        result = _checker().check_consistency(cache, source)
        self.assertFalse(result["consistent"])
        self.assertIn("b", result["stale_keys"])
        self.assertIn("d", result["missing_keys"])
        self.assertIn("c", result["extra_keys"])


class TestFindStaleEntries(unittest.TestCase):
    def test_fresh_entries_not_stale(self):
        now = time.time()
        cache = {"k": "v"}
        timestamps = {"k": now - 10}
        results = _checker().find_stale_entries(cache, timestamps, max_age=3600.0)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["stale"])

    def test_old_entries_are_stale(self):
        now = time.time()
        cache = {"k": "v"}
        timestamps = {"k": now - 7200}
        results = _checker().find_stale_entries(cache, timestamps, max_age=3600.0)
        self.assertTrue(results[0]["stale"])

    def test_missing_timestamp_treated_as_stale(self):
        cache = {"k": "v"}
        results = _checker().find_stale_entries(cache, {}, max_age=3600.0)
        self.assertTrue(results[0]["stale"])

    def test_result_fields_present(self):
        now = time.time()
        cache = {"k": "v"}
        timestamps = {"k": now - 100}
        results = _checker().find_stale_entries(cache, timestamps, max_age=3600.0)
        r = results[0]
        self.assertIn("key", r)
        self.assertIn("age", r)
        self.assertIn("max_age", r)
        self.assertIn("stale", r)


class TestVerifyInvalidation(unittest.TestCase):
    def _evt(self, etype, key, ts):
        return {"type": etype, "key": key, "timestamp": ts}

    def test_correct_set_then_invalidate_sequence(self):
        events = [
            self._evt("set", "x", 1.0),
            self._evt("invalidate", "x", 2.0),
        ]
        result = _checker().verify_invalidation(events)
        self.assertTrue(result["correct"])
        self.assertEqual(result["issues"], [])

    def test_set_without_prior_invalidate_flagged(self):
        events = [
            self._evt("set", "x", 1.0),
            self._evt("set", "x", 2.0),  # second set without invalidation
        ]
        result = _checker().verify_invalidation(events)
        self.assertFalse(result["correct"])

    def test_invalidate_unset_key_flagged(self):
        events = [self._evt("invalidate", "ghost", 1.0)]
        result = _checker().verify_invalidation(events)
        self.assertFalse(result["correct"])

    def test_empty_events_correct(self):
        result = _checker().verify_invalidation([])
        self.assertTrue(result["correct"])

    def test_expire_event_accepted(self):
        events = [
            self._evt("set", "y", 1.0),
            self._evt("expire", "y", 2.0),
        ]
        result = _checker().verify_invalidation(events)
        self.assertTrue(result["correct"])


class TestCheckTtlAccuracy(unittest.TestCase):
    def test_accurate_ttl(self):
        entries = [{"key": "k", "ttl": 60, "created_at": 1000.0, "expected_expiry": 1060.0}]
        results = _checker().check_ttl_accuracy(entries)
        self.assertTrue(results[0]["accurate"])
        self.assertAlmostEqual(results[0]["drift"], 0.0, places=5)

    def test_inaccurate_ttl_large_drift(self):
        entries = [{"key": "k", "ttl": 60, "created_at": 1000.0, "expected_expiry": 1100.0}]
        results = _checker().check_ttl_accuracy(entries)
        self.assertFalse(results[0]["accurate"])
        self.assertAlmostEqual(results[0]["drift"], 40.0, places=5)

    def test_result_fields_present(self):
        entries = [{"key": "k", "ttl": 30, "created_at": 0.0, "expected_expiry": 30.0}]
        results = _checker().check_ttl_accuracy(entries)
        r = results[0]
        self.assertIn("key", r)
        self.assertIn("expected_expiry", r)
        self.assertIn("drift", r)
        self.assertIn("accurate", r)

    def test_empty_entries_returns_empty_list(self):
        results = _checker().check_ttl_accuracy([])
        self.assertEqual(results, [])
