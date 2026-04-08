"""Tests for LeakScanner (Q339)."""
from __future__ import annotations

import unittest

from lidco.stability.leak_scanner import LeakScanner


class TestScanReferences(unittest.TestCase):
    def setUp(self):
        self.scanner = LeakScanner()

    def test_self_append_self_flagged(self):
        code = "self.children.append(self)\n"
        results = self.scanner.scan_references(code)
        self.assertGreater(len(results), 0)

    def test_parent_reference_flagged(self):
        code = "self.parent = node\n"
        results = self.scanner.scan_references(code)
        self.assertTrue(any("parent" in r["description"].lower() for r in results))

    def test_lambda_closes_over_self(self):
        code = "self.callback = lambda x: self.process(x)\n"
        results = self.scanner.scan_references(code)
        self.assertTrue(any("lambda" in r["description"].lower() for r in results))

    def test_event_connect_flagged(self):
        code = "button.connect(self.on_click)\n"
        results = self.scanner.scan_references(code)
        self.assertTrue(any("Event" in r["description"] or "signal" in r["description"].lower() for r in results))

    def test_unbounded_cache_flagged(self):
        code = "_cache = {}\n"
        results = self.scanner.scan_references(code)
        self.assertTrue(any("cache" in r["description"].lower() for r in results))

    def test_result_keys_present(self):
        code = "self.children.append(self)\n"
        results = self.scanner.scan_references(code)
        for r in results:
            self.assertIn("line", r)
            self.assertIn("description", r)
            self.assertIn("risk", r)

    def test_risk_values_valid(self):
        code = "self.parent = node\nself.callback = lambda x: self.process(x)\n"
        results = self.scanner.scan_references(code)
        valid = {"HIGH", "MEDIUM", "LOW"}
        for r in results:
            self.assertIn(r["risk"], valid)

    def test_clean_code_returns_empty(self):
        code = "x = 1\ny = x + 2\n"
        results = self.scanner.scan_references(code)
        self.assertEqual(results, [])


class TestAuditWeakRefs(unittest.TestCase):
    def setUp(self):
        self.scanner = LeakScanner()

    def test_callbacks_list_without_weakref(self):
        code = "self._callbacks = []\n"
        results = self.scanner.audit_weak_refs(code)
        self.assertGreater(len(results), 0)
        self.assertTrue(any("weakref" in r["suggestion"].lower() for r in results))

    def test_parent_strong_ref_without_weakref(self):
        code = "self.parent = parent_node\n"
        results = self.scanner.audit_weak_refs(code)
        self.assertGreater(len(results), 0)

    def test_with_weakref_import_no_audit(self):
        code = "import weakref\nself._callbacks = []\n"
        results = self.scanner.audit_weak_refs(code)
        # weakref already in use → no audit.
        self.assertEqual(results, [])

    def test_result_keys(self):
        code = "self._listeners = []\n"
        results = self.scanner.audit_weak_refs(code)
        for r in results:
            self.assertIn("line", r)
            self.assertIn("pattern", r)
            self.assertIn("suggestion", r)

    def test_cache_without_lru_flagged(self):
        code = "self._cache = {}\n"
        results = self.scanner.audit_weak_refs(code)
        self.assertGreater(len(results), 0)


class TestGetGcStats(unittest.TestCase):
    def setUp(self):
        self.scanner = LeakScanner()

    def test_returns_dict(self):
        stats = self.scanner.get_gc_stats()
        self.assertIsInstance(stats, dict)

    def test_required_keys(self):
        stats = self.scanner.get_gc_stats()
        for key in ("collections", "collected", "uncollectable", "threshold"):
            self.assertIn(key, stats)

    def test_threshold_is_list(self):
        stats = self.scanner.get_gc_stats()
        self.assertIsInstance(stats["threshold"], list)
        self.assertEqual(len(stats["threshold"]), 3)

    def test_numeric_values(self):
        stats = self.scanner.get_gc_stats()
        self.assertIsInstance(stats["collections"], int)
        self.assertIsInstance(stats["collected"], int)
        self.assertIsInstance(stats["uncollectable"], int)


class TestCheckThreshold(unittest.TestCase):
    def setUp(self):
        self.scanner = LeakScanner(threshold_mb=50.0)

    def test_below_threshold_not_exceeded(self):
        result = self.scanner.check_threshold(30.0)
        self.assertFalse(result["exceeded"])

    def test_above_threshold_exceeded(self):
        result = self.scanner.check_threshold(75.0)
        self.assertTrue(result["exceeded"])

    def test_at_threshold_not_exceeded(self):
        result = self.scanner.check_threshold(50.0)
        self.assertFalse(result["exceeded"])

    def test_result_keys(self):
        result = self.scanner.check_threshold(40.0)
        for key in ("exceeded", "current_mb", "threshold_mb", "message"):
            self.assertIn(key, result)

    def test_message_contains_values(self):
        result = self.scanner.check_threshold(80.0)
        self.assertIn("80.0", result["message"])
        self.assertIn("50.0", result["message"])

    def test_custom_threshold(self):
        scanner = LeakScanner(threshold_mb=100.0)
        result = scanner.check_threshold(99.9)
        self.assertFalse(result["exceeded"])
        result2 = scanner.check_threshold(100.1)
        self.assertTrue(result2["exceeded"])


if __name__ == "__main__":
    unittest.main()
