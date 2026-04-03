"""Tests for lidco.streaming.flow_controller — FlowController."""
from __future__ import annotations

import unittest

from lidco.streaming.backpressure import BackpressureController
from lidco.streaming.flow_controller import FlowController
from lidco.streaming.stream_buffer import StreamBuffer


class TestFlowControllerDefaults(unittest.TestCase):
    def test_creates_defaults(self):
        fc = FlowController()
        self.assertFalse(fc.is_congested)
        self.assertAlmostEqual(fc.adaptive_rate(), 1.0, places=1)

    def test_stats_keys(self):
        s = FlowController().stats()
        for key in ("backpressure", "buffer", "produce_count", "consume_count", "rejected_count", "is_congested"):
            self.assertIn(key, s)


class TestProduceConsume(unittest.TestCase):
    def setUp(self):
        self.buf = StreamBuffer(capacity=10)
        self.bp = BackpressureController(buffer_size=10, high_watermark=0.8, low_watermark=0.2)
        self.fc = FlowController(backpressure=self.bp, buffer=self.buf)

    def test_produce_and_consume(self):
        self.assertTrue(self.fc.produce("hello"))
        self.assertEqual(self.fc.consume(1), ["hello"])

    def test_multiple_produce(self):
        for i in range(5):
            self.fc.produce(f"t{i}")
        tokens = self.fc.consume(5)
        self.assertEqual(len(tokens), 5)
        self.assertEqual(tokens[0], "t0")

    def test_produce_rejected_when_paused(self):
        self.bp.pause()
        self.assertFalse(self.fc.produce("x"))
        self.assertEqual(self.fc.stats()["rejected_count"], 1)


class TestCongestion(unittest.TestCase):
    def test_congestion_triggers(self):
        buf = StreamBuffer(capacity=10)
        bp = BackpressureController(buffer_size=10, high_watermark=0.8, low_watermark=0.2)
        fc = FlowController(backpressure=bp, buffer=buf)
        for i in range(8):
            fc.produce(f"t{i}")
        self.assertTrue(fc.is_congested)

    def test_congestion_resolves_after_consume(self):
        buf = StreamBuffer(capacity=10)
        bp = BackpressureController(buffer_size=10, high_watermark=0.8, low_watermark=0.2)
        fc = FlowController(backpressure=bp, buffer=buf)
        for i in range(8):
            fc.produce(f"t{i}")
        fc.consume(7)
        self.assertFalse(fc.is_congested)


class TestAdaptiveRate(unittest.TestCase):
    def test_empty_buffer_full_rate(self):
        self.assertAlmostEqual(FlowController().adaptive_rate(), 1.0, places=1)

    def test_full_buffer_low_rate(self):
        buf = StreamBuffer(capacity=10)
        fc = FlowController(buffer=buf)
        for i in range(10):
            buf.write(f"t{i}")
        self.assertLessEqual(fc.adaptive_rate(), 0.2)

    def test_half_buffer_mid_rate(self):
        buf = StreamBuffer(capacity=10)
        fc = FlowController(buffer=buf)
        for i in range(5):
            buf.write(f"t{i}")
        rate = fc.adaptive_rate()
        self.assertGreater(rate, 0.4)
        self.assertLess(rate, 0.7)


if __name__ == "__main__":
    unittest.main()
