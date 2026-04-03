"""Tests for lidco.streaming.backpressure — BackpressureController."""
from __future__ import annotations

import unittest

from lidco.streaming.backpressure import (
    BackpressureController,
    BackpressureSignal,
    BackpressureState,
)


class TestBackpressureInit(unittest.TestCase):
    def test_defaults(self):
        bp = BackpressureController()
        self.assertFalse(bp.is_paused)
        s = bp.stats()
        self.assertEqual(s["rate"], 1000)
        self.assertEqual(s["state"], "flowing")

    def test_invalid_watermarks(self):
        with self.assertRaises(ValueError):
            BackpressureController(high_watermark=0.2, low_watermark=0.8)

    def test_equal_watermarks(self):
        with self.assertRaises(ValueError):
            BackpressureController(high_watermark=0.5, low_watermark=0.5)

    def test_invalid_buffer_size(self):
        with self.assertRaises(ValueError):
            BackpressureController(buffer_size=0)

    def test_invalid_rate(self):
        with self.assertRaises(ValueError):
            BackpressureController(token_rate_limit=0)


class TestBackpressureCheck(unittest.TestCase):
    def setUp(self):
        self.bp = BackpressureController(
            buffer_size=100, high_watermark=0.8, low_watermark=0.2
        )

    def test_ok_when_below_high(self):
        sig = self.bp.check(50)
        self.assertEqual(sig.action, "ok")
        self.assertAlmostEqual(sig.buffer_usage, 0.5)

    def test_pause_at_high_watermark(self):
        sig = self.bp.check(80)
        self.assertEqual(sig.action, "pause")
        self.assertTrue(self.bp.is_paused)

    def test_ok_while_paused_above_low(self):
        self.bp.check(80)
        sig = self.bp.check(50)
        self.assertEqual(sig.action, "ok")
        self.assertTrue(self.bp.is_paused)

    def test_resume_at_low_watermark(self):
        self.bp.check(80)
        sig = self.bp.check(20)
        self.assertEqual(sig.action, "resume")
        self.assertFalse(self.bp.is_paused)

    def test_resume_below_low(self):
        self.bp.check(80)
        sig = self.bp.check(10)
        self.assertEqual(sig.action, "resume")


class TestManualControl(unittest.TestCase):
    def test_manual_pause(self):
        bp = BackpressureController()
        bp.pause()
        self.assertTrue(bp.is_paused)

    def test_manual_resume(self):
        bp = BackpressureController()
        bp.pause()
        bp.resume()
        self.assertFalse(bp.is_paused)

    def test_double_pause_no_double_count(self):
        bp = BackpressureController()
        bp.pause()
        bp.pause()
        self.assertEqual(bp.stats()["pause_count"], 1)

    def test_double_resume_no_double_count(self):
        bp = BackpressureController()
        bp.pause()
        bp.resume()
        bp.resume()
        self.assertEqual(bp.stats()["resume_count"], 1)


class TestBackpressureStats(unittest.TestCase):
    def test_stats_keys(self):
        s = BackpressureController().stats()
        for key in ("rate", "state", "uptime", "pause_count", "resume_count"):
            self.assertIn(key, s)

    def test_stats_after_operations(self):
        bp = BackpressureController(buffer_size=100, high_watermark=0.8, low_watermark=0.2)
        bp.check(80)
        bp.check(10)
        s = bp.stats()
        self.assertEqual(s["pause_count"], 1)
        self.assertEqual(s["resume_count"], 1)


class TestBackpressureSignal(unittest.TestCase):
    def test_frozen(self):
        sig = BackpressureSignal(action="ok", buffer_usage=0.5)
        self.assertEqual(sig.action, "ok")
        self.assertEqual(sig.buffer_usage, 0.5)


if __name__ == "__main__":
    unittest.main()
