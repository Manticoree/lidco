"""Tests for TraceCollector."""
from __future__ import annotations

import time
import unittest

from lidco.observability.traces import TraceCollector, Span


class TestSpan(unittest.TestCase):
    def test_duration_ms_zero_when_not_ended(self):
        s = Span(span_id="a", trace_id="t", name="op")
        self.assertEqual(s.duration_ms, 0.0)

    def test_duration_ms_positive(self):
        s = Span(span_id="a", trace_id="t", name="op", start_time=1.0, end_time=1.05)
        self.assertAlmostEqual(s.duration_ms, 50.0, places=1)


class TestTraceCollector(unittest.TestCase):
    def setUp(self):
        self.tc = TraceCollector()

    def test_start_span_creates_span(self):
        span = self.tc.start_span("op1")
        self.assertEqual(span.name, "op1")
        self.assertIsNotNone(span.span_id)
        self.assertIsNotNone(span.trace_id)
        self.assertIsNone(span.parent_id)

    def test_start_span_with_parent(self):
        parent = self.tc.start_span("parent")
        child = self.tc.start_span("child", parent=parent.span_id)
        self.assertEqual(child.parent_id, parent.span_id)
        self.assertEqual(child.trace_id, parent.trace_id)

    def test_end_span(self):
        span = self.tc.start_span("op")
        ended = self.tc.end_span(span.span_id)
        self.assertGreater(ended.end_time, 0)
        self.assertIs(ended, span)

    def test_end_span_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.tc.end_span("nonexistent")

    def test_get_trace(self):
        s1 = self.tc.start_span("a")
        s2 = self.tc.start_span("b", parent=s1.span_id)
        spans = self.tc.get_trace(s1.trace_id)
        self.assertEqual(len(spans), 2)
        self.assertEqual(spans[0].name, "a")

    def test_get_trace_empty(self):
        self.assertEqual(self.tc.get_trace("nosuchtrace"), [])

    def test_latency_breakdown(self):
        s1 = self.tc.start_span("db_query")
        self.tc.end_span(s1.span_id)
        breakdown = self.tc.latency_breakdown(s1.trace_id)
        self.assertIn("db_query", breakdown)
        self.assertGreaterEqual(breakdown["db_query"], 0.0)

    def test_service_map(self):
        s1 = self.tc.start_span("api")
        s2 = self.tc.start_span("db", parent=s1.span_id)
        s3 = self.tc.start_span("cache", parent=s1.span_id)
        smap = self.tc.service_map()
        self.assertIn("api", smap)
        self.assertIn("db", smap["api"])
        self.assertIn("cache", smap["api"])

    def test_service_map_empty(self):
        self.tc.start_span("solo")
        self.assertEqual(self.tc.service_map(), {})

    def test_multiple_traces_isolated(self):
        s1 = self.tc.start_span("trace1_op")
        s2 = self.tc.start_span("trace2_op")
        self.assertNotEqual(s1.trace_id, s2.trace_id)
        self.assertEqual(len(self.tc.get_trace(s1.trace_id)), 1)
        self.assertEqual(len(self.tc.get_trace(s2.trace_id)), 1)


if __name__ == "__main__":
    unittest.main()
