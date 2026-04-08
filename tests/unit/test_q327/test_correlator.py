"""Tests for lidco.logintel.correlator — Log Correlator."""

from __future__ import annotations

import unittest

from lidco.logintel.correlator import LogCorrelator, RootCauseChain, Trace, TraceSpan, TimelineEvent
from lidco.logintel.parser import LogEntry, LogFormat


def _entry(ts: str, level: str, msg: str, source: str = "", trace_id: str = "") -> LogEntry:
    fields: dict = {}
    if trace_id:
        fields["trace_id"] = trace_id
    return LogEntry(timestamp=ts, level=level, message=msg, source=source, fields=fields, format=LogFormat.JSON)


class TestTraceSpan(unittest.TestCase):
    def test_entry_count(self) -> None:
        e = _entry("t1", "INFO", "a")
        span = TraceSpan(trace_id="t1", service="api", start="t1", end="t1", entries=(e,))
        self.assertEqual(span.entry_count, 1)

    def test_empty_span(self) -> None:
        span = TraceSpan(trace_id="t1", service="api", start="", end="")
        self.assertEqual(span.entry_count, 0)
        self.assertFalse(span.error)


class TestTrace(unittest.TestCase):
    def test_services(self) -> None:
        spans = [
            TraceSpan(trace_id="t1", service="api", start="", end=""),
            TraceSpan(trace_id="t1", service="db", start="", end=""),
        ]
        trace = Trace(trace_id="t1", spans=spans)
        self.assertEqual(trace.services, ["api", "db"])

    def test_has_error(self) -> None:
        spans = [
            TraceSpan(trace_id="t1", service="api", start="", end="", error=True),
        ]
        self.assertTrue(Trace(trace_id="t1", spans=spans).has_error)

    def test_no_error(self) -> None:
        spans = [
            TraceSpan(trace_id="t1", service="api", start="", end="", error=False),
        ]
        self.assertFalse(Trace(trace_id="t1", spans=spans).has_error)

    def test_entry_count(self) -> None:
        e1 = _entry("t1", "INFO", "a")
        e2 = _entry("t2", "INFO", "b")
        spans = [
            TraceSpan(trace_id="t1", service="api", start="", end="", entries=(e1,)),
            TraceSpan(trace_id="t1", service="db", start="", end="", entries=(e2,)),
        ]
        self.assertEqual(Trace(trace_id="t1", spans=spans).entry_count, 2)


class TestLogCorrelator(unittest.TestCase):
    def setUp(self) -> None:
        self.correlator = LogCorrelator()

    def test_add_entries(self) -> None:
        entries = [_entry("t1", "INFO", "a", trace_id="abc")]
        self.correlator.add_entries(entries)
        self.assertEqual(self.correlator.entry_count, 1)

    def test_add_entries_appends(self) -> None:
        self.correlator.add_entries([_entry("t1", "INFO", "a")])
        self.correlator.add_entries([_entry("t2", "INFO", "b")])
        self.assertEqual(self.correlator.entry_count, 2)

    def test_correlate_groups_by_trace(self) -> None:
        entries = [
            _entry("t1", "INFO", "req start", source="api", trace_id="abc"),
            _entry("t2", "INFO", "db query", source="db", trace_id="abc"),
            _entry("t3", "INFO", "other", source="api", trace_id="def"),
        ]
        self.correlator.add_entries(entries)
        traces = self.correlator.correlate()
        self.assertEqual(len(traces), 2)
        trace_ids = {t.trace_id for t in traces}
        self.assertEqual(trace_ids, {"abc", "def"})

    def test_correlate_ignores_no_trace_id(self) -> None:
        entries = [_entry("t1", "INFO", "no trace")]
        self.correlator.add_entries(entries)
        traces = self.correlator.correlate()
        self.assertEqual(len(traces), 0)

    def test_correlate_spans_by_service(self) -> None:
        entries = [
            _entry("t1", "INFO", "a", source="api", trace_id="abc"),
            _entry("t2", "ERROR", "b", source="db", trace_id="abc"),
        ]
        self.correlator.add_entries(entries)
        traces = self.correlator.correlate()
        self.assertEqual(len(traces), 1)
        self.assertEqual(len(traces[0].spans), 2)
        services = {s.service for s in traces[0].spans}
        self.assertEqual(services, {"api", "db"})

    def test_correlate_error_span(self) -> None:
        entries = [
            _entry("t1", "ERROR", "fail", source="api", trace_id="abc"),
        ]
        self.correlator.add_entries(entries)
        traces = self.correlator.correlate()
        self.assertTrue(traces[0].has_error)

    # -- Timeline ----------------------------------------------------------

    def test_build_timeline(self) -> None:
        entries = [
            _entry("2026-01-01T00:02:00", "INFO", "second", source="api"),
            _entry("2026-01-01T00:01:00", "INFO", "first", source="db"),
        ]
        self.correlator.add_entries(entries)
        timeline = self.correlator.build_timeline()
        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[0].message, "first")
        self.assertEqual(timeline[1].message, "second")

    def test_build_timeline_filtered(self) -> None:
        entries = [
            _entry("t1", "INFO", "a", trace_id="abc"),
            _entry("t2", "INFO", "b", trace_id="def"),
        ]
        self.correlator.add_entries(entries)
        timeline = self.correlator.build_timeline(trace_id="abc")
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0].message, "a")

    # -- Root cause --------------------------------------------------------

    def test_find_root_cause(self) -> None:
        entries = [
            _entry("t1", "INFO", "request received", source="api", trace_id="abc"),
            _entry("t2", "INFO", "querying db", source="db", trace_id="abc"),
            _entry("t3", "ERROR", "connection refused", source="db", trace_id="abc"),
        ]
        self.correlator.add_entries(entries)
        chain = self.correlator.find_root_cause("abc")
        self.assertIsNotNone(chain)
        self.assertEqual(chain.root_cause, "connection refused")
        self.assertEqual(chain.depth, 3)

    def test_find_root_cause_no_errors(self) -> None:
        entries = [_entry("t1", "INFO", "ok", trace_id="abc")]
        self.correlator.add_entries(entries)
        self.assertIsNone(self.correlator.find_root_cause("abc"))

    def test_find_root_cause_unknown_trace(self) -> None:
        self.assertIsNone(self.correlator.find_root_cause("nonexistent"))

    # -- Service map -------------------------------------------------------

    def test_service_map(self) -> None:
        entries = [
            _entry("t1", "INFO", "a", source="api"),
            _entry("t2", "INFO", "b", source="api"),
            _entry("t3", "INFO", "c", source="db"),
        ]
        self.correlator.add_entries(entries)
        smap = self.correlator.service_map()
        self.assertEqual(smap["api"], 2)
        self.assertEqual(smap["db"], 1)

    def test_service_map_unknown(self) -> None:
        entries = [_entry("t1", "INFO", "a")]
        self.correlator.add_entries(entries)
        smap = self.correlator.service_map()
        self.assertIn("unknown", smap)

    # -- Custom trace field ------------------------------------------------

    def test_custom_trace_field(self) -> None:
        correlator = LogCorrelator(trace_field="request_id")
        e = LogEntry(timestamp="t1", level="INFO", message="a", fields={"request_id": "r1"}, format=LogFormat.JSON)
        correlator.add_entries([e])
        traces = correlator.correlate()
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].trace_id, "r1")


if __name__ == "__main__":
    unittest.main()
