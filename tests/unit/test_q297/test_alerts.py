"""Tests for AlertManager2."""
from __future__ import annotations

import time
import unittest

from lidco.observability.alerts import AlertManager2, AlertSeverity, Rule, Alert


class TestRule(unittest.TestCase):
    def test_is_silenced_false(self):
        r = Rule(rule_id="r1", name="t", condition="gt", threshold=10.0)
        self.assertFalse(r.is_silenced)

    def test_is_silenced_true(self):
        r = Rule(
            rule_id="r1", name="t", condition="gt", threshold=10.0,
            silenced_until=time.time() + 3600,
        )
        self.assertTrue(r.is_silenced)


class TestAlertManager2(unittest.TestCase):
    def setUp(self):
        self.mgr = AlertManager2()

    def test_add_rule(self):
        rule = self.mgr.add_rule("high_cpu", "gt", 90.0, metric_name="cpu")
        self.assertEqual(rule.name, "high_cpu")
        self.assertEqual(rule.condition, "gt")
        self.assertEqual(rule.threshold, 90.0)
        self.assertIn(rule.rule_id, self.mgr._rules)

    def test_evaluate_fires_alert(self):
        self.mgr.add_rule("high", "gt", 80.0, metric_name="cpu")
        alerts = self.mgr.evaluate("cpu", 95.0)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].rule_name, "high")
        self.assertEqual(alerts[0].value, 95.0)

    def test_evaluate_no_fire(self):
        self.mgr.add_rule("high", "gt", 80.0, metric_name="cpu")
        alerts = self.mgr.evaluate("cpu", 50.0)
        self.assertEqual(len(alerts), 0)

    def test_evaluate_conditions(self):
        self.mgr.add_rule("gte", "gte", 80.0)
        self.mgr.add_rule("lt", "lt", 10.0)
        self.mgr.add_rule("lte", "lte", 5.0)
        self.mgr.add_rule("eq", "eq", 42.0)
        self.assertEqual(len(self.mgr.evaluate("x", 80.0)), 1)  # gte
        self.assertEqual(len(self.mgr.evaluate("x", 5.0)), 2)   # lt yes, lte yes
        # Reset for clean test
        mgr2 = AlertManager2()
        mgr2.add_rule("eq_only", "eq", 42.0)
        self.assertEqual(len(mgr2.evaluate("x", 42.0)), 1)
        self.assertEqual(len(mgr2.evaluate("x", 43.0)), 0)

    def test_evaluate_respects_metric_name(self):
        self.mgr.add_rule("cpu_high", "gt", 90.0, metric_name="cpu")
        alerts = self.mgr.evaluate("memory", 99.0)
        self.assertEqual(len(alerts), 0)

    def test_silence_prevents_firing(self):
        rule = self.mgr.add_rule("high", "gt", 80.0, metric_name="cpu")
        self.mgr.silence(rule.rule_id, 3600)
        alerts = self.mgr.evaluate("cpu", 99.0)
        self.assertEqual(len(alerts), 0)

    def test_silence_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.mgr.silence("no_such_rule", 60)

    def test_active_alerts(self):
        self.mgr.add_rule("h", "gt", 0.0)
        self.mgr.evaluate("x", 1.0)
        active = self.mgr.active_alerts()
        self.assertEqual(len(active), 1)

    def test_escalate(self):
        self.mgr.add_rule("h", "gt", 0.0)
        alerts = self.mgr.evaluate("x", 1.0)
        alert_id = alerts[0].alert_id
        self.assertTrue(self.mgr.escalate(alert_id))
        # After escalation it should not appear in active_alerts
        self.assertEqual(len(self.mgr.active_alerts()), 0)

    def test_escalate_not_found(self):
        self.assertFalse(self.mgr.escalate("nonexistent"))

    def test_severity_default(self):
        rule = self.mgr.add_rule("warn_rule", "gt", 50.0)
        self.assertEqual(rule.severity, AlertSeverity.WARNING)

    def test_severity_custom(self):
        rule = self.mgr.add_rule("crit", "gt", 99.0, severity=AlertSeverity.CRITICAL)
        self.assertEqual(rule.severity, AlertSeverity.CRITICAL)


if __name__ == "__main__":
    unittest.main()
