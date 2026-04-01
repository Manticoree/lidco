"""Tests for budget.dynamic_scaler."""
from __future__ import annotations

import unittest

from lidco.budget.dynamic_scaler import DynamicScaler, ScaleConfig, ScaleDecision


class TestScaleConfig(unittest.TestCase):
    def test_frozen(self):
        c = ScaleConfig()
        with self.assertRaises(AttributeError):
            c.min_tokens = 0  # type: ignore[misc]

    def test_defaults(self):
        c = ScaleConfig()
        self.assertEqual(c.min_tokens, 512)
        self.assertEqual(c.max_tokens, 16384)
        self.assertEqual(c.default_tokens, 4096)
        self.assertAlmostEqual(c.learning_rate, 0.1)


class TestScaleDecision(unittest.TestCase):
    def test_frozen(self):
        d = ScaleDecision(requested=100, adjusted=200)
        with self.assertRaises(AttributeError):
            d.adjusted = 300  # type: ignore[misc]


class TestDynamicScaler(unittest.TestCase):
    def setUp(self):
        self.scaler = DynamicScaler()

    def test_simple_factor(self):
        d = self.scaler.scale(0.1, 4096)
        self.assertEqual(d.adjusted, 1024)  # 0.25x

    def test_moderate_factor(self):
        d = self.scaler.scale(0.3, 4096)
        self.assertEqual(d.adjusted, 4096)  # 1.0x

    def test_complex_factor(self):
        d = self.scaler.scale(0.6, 4096)
        self.assertEqual(d.adjusted, 8192)  # 2.0x

    def test_expert_factor(self):
        d = self.scaler.scale(0.9, 4096)
        self.assertEqual(d.adjusted, 16384)  # 4.0x

    def test_clamp_min(self):
        d = self.scaler.scale(0.1, 100)  # 100 * 0.25 = 25 < 512
        self.assertEqual(d.adjusted, 512)

    def test_clamp_max(self):
        d = self.scaler.scale(0.9, 10000)  # 40000 > 16384
        self.assertEqual(d.adjusted, 16384)

    def test_record_and_utilization(self):
        self.assertAlmostEqual(self.scaler.average_utilization(), 0.0)
        self.scaler.record_actual(1000, 500)
        self.scaler.record_actual(1000, 300)
        self.assertAlmostEqual(self.scaler.average_utilization(), 0.4)

    def test_adjust_from_history_low_util(self):
        self.scaler.record_actual(1000, 400)
        adjusted = self.scaler.adjust_from_history(4096)
        self.assertLess(adjusted, 4096)

    def test_adjust_from_history_high_util(self):
        self.scaler.record_actual(1000, 950)
        adjusted = self.scaler.adjust_from_history(4096)
        self.assertGreater(adjusted, 4096)

    def test_summary(self):
        text = self.scaler.summary()
        self.assertIn("DynamicScaler", text)
        self.assertIn("history=0", text)


if __name__ == "__main__":
    unittest.main()
