"""Tests for LogAnalyzer2."""
from __future__ import annotations

import unittest

from lidco.observability.log_analyzer import LogAnalyzer2, LogPattern, ErrorCluster


class TestLogPattern(unittest.TestCase):
    def test_defaults(self):
        p = LogPattern(pattern="ERROR", count=5)
        self.assertEqual(p.severity, "info")
        self.assertEqual(p.examples, [])


class TestErrorCluster(unittest.TestCase):
    def test_fields(self):
        c = ErrorCluster(key="k", count=2, lines=["a", "b"])
        self.assertEqual(c.count, 2)


class TestLogAnalyzer2(unittest.TestCase):
    def setUp(self):
        self.la = LogAnalyzer2()

    def test_ingest_returns_count(self):
        count = self.la.ingest(["INFO hello", "ERROR fail", ""])
        self.assertEqual(count, 2)

    def test_ingest_skips_blank(self):
        self.la.ingest(["", "  ", ""])
        self.assertEqual(len(self.la._lines), 0)

    def test_ingest_collects_errors(self):
        self.la.ingest(["ERROR something", "INFO ok", "CRITICAL boom"])
        self.assertEqual(len(self.la._error_lines), 2)

    def test_detect_patterns(self):
        self.la.ingest(["INFO a", "INFO b", "ERROR c"])
        pats = self.la.detect_patterns()
        names = [p.pattern for p in pats]
        self.assertIn("INFO", names)
        self.assertIn("ERROR", names)

    def test_detect_patterns_most_common_first(self):
        self.la.ingest(["INFO a", "INFO b", "INFO c", "ERROR d"])
        pats = self.la.detect_patterns()
        self.assertEqual(pats[0].pattern, "INFO")
        self.assertEqual(pats[0].count, 3)

    def test_cluster_errors(self):
        self.la.ingest([
            "ERROR connection refused at 10.0.0.1",
            "ERROR connection refused at 10.0.0.2",
            "ERROR timeout after 30s",
        ])
        clusters = self.la.cluster_errors()
        self.assertGreaterEqual(len(clusters), 1)
        # Connection refused cluster should be largest
        self.assertEqual(clusters[0].count, 2)

    def test_suggest_root_cause_timeout(self):
        result = self.la.suggest_root_cause("request timeout after 30s")
        self.assertIn("timeout", result.lower())

    def test_suggest_root_cause_connection(self):
        result = self.la.suggest_root_cause("connection refused by host")
        self.assertIn("service", result.lower())

    def test_suggest_root_cause_permission(self):
        result = self.la.suggest_root_cause("permission denied")
        self.assertIn("permission", result.lower())

    def test_suggest_root_cause_memory(self):
        result = self.la.suggest_root_cause("OOM killed process")
        self.assertIn("memory", result.lower())

    def test_suggest_root_cause_disk(self):
        result = self.la.suggest_root_cause("no space left on device")
        self.assertIn("disk", result.lower())

    def test_suggest_root_cause_unknown(self):
        result = self.la.suggest_root_cause("some weird error")
        self.assertIn("unknown", result.lower())

    def test_summary(self):
        self.la.ingest(["INFO a", "ERROR b"])
        s = self.la.summary()
        self.assertEqual(s["total_lines"], 2)
        self.assertEqual(s["error_lines"], 1)
        self.assertIn("patterns", s)
        self.assertIn("error_clusters", s)


if __name__ == "__main__":
    unittest.main()
