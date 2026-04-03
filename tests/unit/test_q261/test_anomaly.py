"""Tests for AnomalyDetector."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.audit.anomaly import Anomaly, AnomalyDetector
from lidco.audit.event_store import AuditEventStore


class TestAnomalyDetector(unittest.TestCase):
    def setUp(self):
        self.store = AuditEventStore()
        self.detector = AnomalyDetector(self.store)

    def test_no_anomalies_empty_store(self):
        result = self.detector.detect_all()
        self.assertEqual(len(result), 0)

    def test_privilege_escalation_rapid(self):
        base = time.time()
        with patch("lidco.audit.event_store.time.time", side_effect=[base, base + 10]):
            self.store.append("admin", "mallory", "role_change", "/users/mallory")
            self.store.append("admin", "mallory", "grant_admin", "/users/mallory")
        results = self.detector.detect_privilege_escalation()
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].type, "privilege_escalation")
        self.assertEqual(results[0].severity, "critical")

    def test_privilege_escalation_single(self):
        self.store.append("admin", "bob", "grant_admin", "/users/bob")
        results = self.detector.detect_privilege_escalation()
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].severity, "high")

    def test_no_privilege_escalation_normal(self):
        self.store.append("auth", "alice", "login", "/session")
        results = self.detector.detect_privilege_escalation()
        self.assertEqual(len(results), 0)

    def test_off_hours_detection(self):
        # Create an event at 3 AM
        from datetime import datetime
        target = datetime(2025, 6, 15, 3, 0, 0)
        ts = target.timestamp()
        with patch("lidco.audit.event_store.time.time", return_value=ts):
            self.store.append("auth", "nightowl", "login", "/session")
        results = self.detector.detect_off_hours(business_hours=(9, 17))
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].type, "off_hours")

    def test_off_hours_inside_business(self):
        from datetime import datetime
        target = datetime(2025, 6, 15, 12, 0, 0)
        ts = target.timestamp()
        with patch("lidco.audit.event_store.time.time", return_value=ts):
            self.store.append("auth", "worker", "login", "/session")
        results = self.detector.detect_off_hours(business_hours=(9, 17))
        self.assertEqual(len(results), 0)

    def test_bulk_operations_detected(self):
        base = time.time()
        times = [base + i for i in range(60)]
        with patch("lidco.audit.event_store.time.time", side_effect=times):
            for i in range(60):
                self.store.append("data", "spammer", "write", f"/file{i}")
        results = self.detector.detect_bulk_operations(threshold=50)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].type, "bulk_operations")

    def test_bulk_operations_below_threshold(self):
        for i in range(5):
            self.store.append("data", "normal", "write", f"/file{i}")
        results = self.detector.detect_bulk_operations(threshold=50)
        self.assertEqual(len(results), 0)

    def test_detect_all_caches(self):
        self.store.append("admin", "bob", "grant_admin", "/users/bob")
        self.detector.detect_all()
        cached = self.detector.anomalies()
        self.assertTrue(len(cached) >= 1)

    def test_anomalies_empty_before_detect(self):
        self.assertEqual(self.detector.anomalies(), [])

    def test_summary(self):
        self.store.append("admin", "bob", "grant_admin", "/users/bob")
        self.detector.detect_all()
        s = self.detector.summary()
        self.assertIn("total_anomalies", s)
        self.assertIn("by_type", s)
        self.assertIn("by_severity", s)

    def test_custom_thresholds(self):
        detector = AnomalyDetector(self.store, thresholds={"bulk_count": 3, "bulk_window_seconds": 600})
        base = time.time()
        times = [base + i for i in range(5)]
        with patch("lidco.audit.event_store.time.time", side_effect=times):
            for i in range(5):
                self.store.append("data", "user", "write", f"/f{i}")
        results = detector.detect_bulk_operations(threshold=3)
        self.assertTrue(len(results) >= 1)

    def test_anomaly_frozen(self):
        a = Anomaly(type="test", severity="low", description="d", actor="a", timestamp=0.0, evidence=[])
        with self.assertRaises(AttributeError):
            a.type = "changed"  # type: ignore[misc]
