"""Tests for budget.threshold_alerter — AlertLevel, ThresholdAlert, ThresholdAlerter."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.budget.threshold_alerter import (
    AlertLevel,
    ThresholdAlert,
    ThresholdAlerter,
)


class TestAlertLevel(unittest.TestCase):
    def test_values(self):
        self.assertEqual(AlertLevel.INFO, "INFO")
        self.assertEqual(AlertLevel.WARNING, "WARNING")
        self.assertEqual(AlertLevel.CRITICAL, "CRITICAL")


class TestThresholdAlert(unittest.TestCase):
    def test_frozen(self):
        alert = ThresholdAlert(
            level=AlertLevel.INFO, threshold=0.7, current=0.72, message="test"
        )
        with self.assertRaises(AttributeError):
            alert.level = AlertLevel.CRITICAL  # type: ignore[misc]


class TestThresholdAlerter(unittest.TestCase):
    def setUp(self):
        self.alerter = ThresholdAlerter(thresholds=(0.70, 0.85, 0.95))
        # Zero out cooldown for testing
        self.alerter._cooldown = 0.0

    def test_no_alert_below_threshold(self):
        result = self.alerter.check(0.50)
        self.assertIsNone(result)

    def test_alert_on_first_threshold(self):
        alert = self.alerter.check(0.72)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.level, AlertLevel.INFO)
        self.assertAlmostEqual(alert.threshold, 0.70)

    def test_alert_on_warning_threshold(self):
        alert = self.alerter.check(0.88)
        self.assertIsNotNone(alert)
        # Highest crossed threshold is 0.85 => WARNING
        self.assertEqual(alert.level, AlertLevel.WARNING)

    def test_alert_on_critical_threshold(self):
        alert = self.alerter.check(0.96)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.level, AlertLevel.CRITICAL)

    def test_cooldown_prevents_duplicate(self):
        alerter = ThresholdAlerter(thresholds=(0.70,))
        alerter._cooldown = 9999.0  # very long cooldown
        alert1 = alerter.check(0.75)
        self.assertIsNotNone(alert1)
        alert2 = alerter.check(0.80)
        self.assertIsNone(alert2)  # still in cooldown

    def test_get_alerts(self):
        self.alerter.check(0.72)
        self.alerter.check(0.88)
        alerts = self.alerter.get_alerts()
        self.assertEqual(len(alerts), 2)

    def test_reset(self):
        self.alerter.check(0.72)
        self.alerter.reset()
        self.assertEqual(len(self.alerter.get_alerts()), 0)
        # Can fire again after reset
        alert = self.alerter.check(0.72)
        self.assertIsNotNone(alert)

    def test_set_thresholds(self):
        self.alerter.set_thresholds((0.50, 0.90))
        alert = self.alerter.check(0.55)
        self.assertIsNotNone(alert)

    def test_is_critical(self):
        self.assertTrue(self.alerter.is_critical(0.96))
        self.assertFalse(self.alerter.is_critical(0.90))

    def test_summary(self):
        s = self.alerter.summary()
        self.assertIn("Threshold Alerter", s)
        self.assertIn("70%", s)
        self.assertIn("85%", s)
        self.assertIn("95%", s)


if __name__ == "__main__":
    unittest.main()
