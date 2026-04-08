"""Tests for lidco.logintel.dashboard — Log Dashboard."""

from __future__ import annotations

import json
import unittest

from lidco.logintel.dashboard import (
    DashboardData,
    LogDashboard,
    ServiceSummary,
    TopError,
    VolumePoint,
)
from lidco.logintel.parser import LogEntry, LogFormat


def _entry(ts: str = "2026-01-01T12:00:00", level: str = "INFO", msg: str = "ok", source: str = "api") -> LogEntry:
    return LogEntry(timestamp=ts, level=level, message=msg, source=source, format=LogFormat.JSON)


class TestVolumePoint(unittest.TestCase):
    def test_error_rate(self) -> None:
        vp = VolumePoint(bucket="2026-01-01T12", count=10, error_count=3)
        self.assertAlmostEqual(vp.error_rate, 0.3)

    def test_error_rate_zero(self) -> None:
        vp = VolumePoint(bucket="b", count=0)
        self.assertEqual(vp.error_rate, 0.0)


class TestServiceSummary(unittest.TestCase):
    def test_error_rate(self) -> None:
        s = ServiceSummary(service="api", total=20, error_count=4, warn_count=2)
        self.assertAlmostEqual(s.error_rate, 0.2)

    def test_error_rate_zero(self) -> None:
        s = ServiceSummary(service="api", total=0, error_count=0, warn_count=0)
        self.assertEqual(s.error_rate, 0.0)


class TestDashboardData(unittest.TestCase):
    def test_error_rate(self) -> None:
        d = DashboardData(total_entries=100, error_count=5)
        self.assertAlmostEqual(d.error_rate, 0.05)

    def test_error_rate_zero(self) -> None:
        self.assertEqual(DashboardData().error_rate, 0.0)


class TestLogDashboard(unittest.TestCase):
    def setUp(self) -> None:
        self.dashboard = LogDashboard()

    def test_build_empty(self) -> None:
        data = self.dashboard.build([])
        self.assertEqual(data.total_entries, 0)

    def test_build_counts(self) -> None:
        entries = [
            _entry(level="INFO"),
            _entry(level="ERROR", msg="fail1"),
            _entry(level="WARNING"),
            _entry(level="CRITICAL", msg="fail2"),
        ]
        data = self.dashboard.build(entries)
        self.assertEqual(data.total_entries, 4)
        self.assertEqual(data.error_count, 2)
        self.assertEqual(data.warn_count, 1)

    def test_build_top_errors(self) -> None:
        entries = [
            _entry(level="ERROR", msg="err A"),
            _entry(level="ERROR", msg="err A"),
            _entry(level="ERROR", msg="err B"),
        ]
        data = self.dashboard.build(entries)
        self.assertEqual(len(data.top_errors), 2)
        self.assertEqual(data.top_errors[0].message, "err A")
        self.assertEqual(data.top_errors[0].count, 2)

    def test_build_top_n_limit(self) -> None:
        dashboard = LogDashboard(top_n=1)
        entries = [
            _entry(level="ERROR", msg="err A"),
            _entry(level="ERROR", msg="err B"),
        ]
        data = dashboard.build(entries)
        self.assertEqual(len(data.top_errors), 1)

    def test_build_volume_chart(self) -> None:
        entries = [
            _entry(ts="2026-01-01T12:00:00", level="INFO"),
            _entry(ts="2026-01-01T12:30:00", level="ERROR", msg="e"),
            _entry(ts="2026-01-01T13:00:00", level="INFO"),
        ]
        data = self.dashboard.build(entries)
        self.assertGreaterEqual(len(data.volume_chart), 1)

    def test_build_services(self) -> None:
        entries = [
            _entry(source="api", level="INFO"),
            _entry(source="api", level="ERROR", msg="e"),
            _entry(source="db", level="INFO"),
        ]
        data = self.dashboard.build(entries)
        self.assertEqual(len(data.services), 2)
        api_svc = [s for s in data.services if s.service == "api"][0]
        self.assertEqual(api_svc.total, 2)
        self.assertEqual(api_svc.error_count, 1)

    def test_build_timeline_range(self) -> None:
        entries = [
            _entry(ts="2026-01-01T10:00:00"),
            _entry(ts="2026-01-01T14:00:00"),
        ]
        data = self.dashboard.build(entries)
        self.assertEqual(data.timeline_start, "2026-01-01T10:00:00")
        self.assertEqual(data.timeline_end, "2026-01-01T14:00:00")

    # -- Drill-down --------------------------------------------------------

    def test_drill_down_by_service(self) -> None:
        entries = [_entry(source="api"), _entry(source="db")]
        filtered = self.dashboard.drill_down(entries, service="api")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].source, "api")

    def test_drill_down_by_level(self) -> None:
        entries = [_entry(level="INFO"), _entry(level="ERROR", msg="e")]
        filtered = self.dashboard.drill_down(entries, level="ERROR")
        self.assertEqual(len(filtered), 1)

    def test_drill_down_combined(self) -> None:
        entries = [
            _entry(source="api", level="ERROR", msg="e"),
            _entry(source="api", level="INFO"),
            _entry(source="db", level="ERROR", msg="e"),
        ]
        filtered = self.dashboard.drill_down(entries, service="api", level="ERROR")
        self.assertEqual(len(filtered), 1)

    # -- Export ------------------------------------------------------------

    def test_export_json(self) -> None:
        entries = [_entry(level="ERROR", msg="fail")]
        data = self.dashboard.build(entries)
        exported = self.dashboard.export_json(data)
        parsed = json.loads(exported)
        self.assertEqual(parsed["total_entries"], 1)
        self.assertEqual(parsed["error_count"], 1)
        self.assertIn("volume_chart", parsed)
        self.assertIn("services", parsed)

    def test_export_text(self) -> None:
        entries = [_entry(level="ERROR", msg="fail"), _entry(level="INFO")]
        data = self.dashboard.build(entries)
        text = self.dashboard.export_text(data)
        self.assertIn("Log Dashboard", text)
        self.assertIn("Errors:", text)
        self.assertIn("Top Errors:", text)


if __name__ == "__main__":
    unittest.main()
