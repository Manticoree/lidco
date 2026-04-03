"""Tests for AuditDashboard."""
from __future__ import annotations

import unittest

from lidco.audit.anomaly import AnomalyDetector
from lidco.audit.dashboard import AuditDashboard, DashboardMetrics
from lidco.audit.event_store import AuditEventStore


class TestAuditDashboard(unittest.TestCase):
    def setUp(self):
        self.store = AuditEventStore()
        self.detector = AnomalyDetector(self.store)
        self.dashboard = AuditDashboard(self.store, self.detector)
        # Seed some events
        for i in range(5):
            self.store.append("auth", "alice", "login", "/session")
        for i in range(3):
            self.store.append("data", "bob", "read", "/file")
        self.store.append("admin", "carol", "grant_admin", "/users")

    def test_metrics_returns_dataclass(self):
        m = self.dashboard.metrics()
        self.assertIsInstance(m, DashboardMetrics)
        self.assertEqual(m.total_events, 9)
        self.assertEqual(m.active_actors, 3)

    def test_risk_score_no_anomalies(self):
        score = self.dashboard.risk_score()
        # No detect_all called yet, so anomalies list is empty
        self.assertEqual(score, 0.0)

    def test_risk_score_with_anomalies(self):
        self.detector.detect_all()
        score = self.dashboard.risk_score()
        # carol's grant_admin triggers at least one anomaly
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_risk_score_no_detector(self):
        dashboard = AuditDashboard(self.store, detector=None)
        self.assertEqual(dashboard.risk_score(), 0.0)

    def test_recent(self):
        recent = self.dashboard.recent(limit=5)
        self.assertEqual(len(recent), 5)

    def test_recent_fewer_than_limit(self):
        small_store = AuditEventStore()
        small_store.append("auth", "x", "y", "z")
        d = AuditDashboard(small_store)
        self.assertEqual(len(d.recent(limit=20)), 1)

    def test_actor_activity(self):
        info = self.dashboard.actor_activity("alice")
        self.assertEqual(info["actor"], "alice")
        self.assertEqual(info["event_count"], 5)
        self.assertGreater(info["last_active"], 0.0)

    def test_actor_activity_unknown(self):
        info = self.dashboard.actor_activity("unknown")
        self.assertEqual(info["event_count"], 0)

    def test_render_text(self):
        text = self.dashboard.render_text()
        self.assertIn("Audit Dashboard", text)
        self.assertIn("Total events", text)
        self.assertIn("alice", text)

    def test_summary(self):
        s = self.dashboard.summary()
        self.assertIn("total_events", s)
        self.assertIn("risk_score", s)
        self.assertEqual(s["total_events"], 9)

    def test_top_actors_sorted(self):
        m = self.dashboard.metrics()
        # alice has 5, bob has 3, carol has 1
        self.assertEqual(m.top_actors[0][0], "alice")
        self.assertEqual(m.top_actors[0][1], 5)
