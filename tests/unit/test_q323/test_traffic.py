"""Tests for lidco.mesh.traffic — TrafficAnalyzer."""

from __future__ import annotations

import unittest

from lidco.mesh.traffic import (
    PairSummary,
    TrafficAnalyzer,
    TrafficPattern,
    TrafficRecord,
    TrafficReport,
)


class TestTrafficRecord(unittest.TestCase):
    def test_defaults(self) -> None:
        rec = TrafficRecord(source="a", target="b", timestamp=1.0, latency_ms=10.0)
        self.assertEqual(rec.status_code, 200)
        self.assertEqual(rec.request_size_bytes, 0)

    def test_frozen(self) -> None:
        rec = TrafficRecord(source="a", target="b", timestamp=1.0, latency_ms=10.0)
        with self.assertRaises(AttributeError):
            rec.source = "x"  # type: ignore[misc]


class TestTrafficAnalyzer(unittest.TestCase):
    def _make_records(self) -> list[TrafficRecord]:
        records = []
        for i in range(20):
            records.append(TrafficRecord(
                source="api", target="db",
                timestamp=float(i), latency_ms=10.0 + i,
                status_code=200 if i < 18 else 500,
            ))
        for i in range(5):
            records.append(TrafficRecord(
                source="api", target="cache",
                timestamp=float(i), latency_ms=2.0,
            ))
        return records

    def test_add_record(self) -> None:
        analyzer = TrafficAnalyzer()
        analyzer.add_record(TrafficRecord(source="a", target="b", timestamp=0, latency_ms=1))
        self.assertEqual(analyzer.record_count, 1)

    def test_add_records(self) -> None:
        analyzer = TrafficAnalyzer()
        analyzer.add_records(self._make_records())
        self.assertEqual(analyzer.record_count, 25)

    def test_analyze_empty(self) -> None:
        analyzer = TrafficAnalyzer()
        report = analyzer.analyze()
        self.assertEqual(report.total_records, 0)
        self.assertEqual(len(report.pairs), 0)

    def test_analyze_basic(self) -> None:
        analyzer = TrafficAnalyzer(records=self._make_records())
        report = analyzer.analyze()
        self.assertIsInstance(report, TrafficReport)
        self.assertEqual(report.total_records, 25)
        self.assertEqual(len(report.pairs), 2)

    def test_pair_summary_fields(self) -> None:
        analyzer = TrafficAnalyzer(records=self._make_records())
        report = analyzer.analyze()
        db_pair = next(p for p in report.pairs if p.target == "db")
        self.assertEqual(db_pair.total_requests, 20)
        self.assertGreater(db_pair.avg_latency_ms, 0)
        self.assertGreater(db_pair.p50_latency_ms, 0)
        self.assertGreater(db_pair.p99_latency_ms, 0)
        self.assertGreater(db_pair.error_rate, 0)

    def test_top_talkers(self) -> None:
        analyzer = TrafficAnalyzer(records=self._make_records())
        report = analyzer.analyze()
        self.assertIn("api", report.top_talkers)

    def test_volume_for(self) -> None:
        analyzer = TrafficAnalyzer(records=self._make_records())
        self.assertEqual(analyzer.volume_for("api", "db"), 20)
        self.assertEqual(analyzer.volume_for("api", "cache"), 5)
        self.assertEqual(analyzer.volume_for("db", "api"), 0)

    def test_error_rate_for(self) -> None:
        analyzer = TrafficAnalyzer(records=self._make_records())
        rate = analyzer.error_rate_for("api", "db")
        self.assertAlmostEqual(rate, 2 / 20)
        self.assertEqual(analyzer.error_rate_for("api", "cache"), 0.0)
        self.assertEqual(analyzer.error_rate_for("x", "y"), 0.0)

    def test_sorted_by_request_count(self) -> None:
        analyzer = TrafficAnalyzer(records=self._make_records())
        report = analyzer.analyze()
        # db pair has 20, cache has 5 — db should be first
        self.assertEqual(report.pairs[0].target, "db")

    def test_pattern_detection_steady(self) -> None:
        records = [
            TrafficRecord(source="a", target="b", timestamp=float(i), latency_ms=5)
            for i in range(10)
        ]
        analyzer = TrafficAnalyzer(records=records)
        report = analyzer.analyze()
        self.assertEqual(report.pairs[0].pattern, TrafficPattern.STEADY)

    def test_pattern_detection_bursty(self) -> None:
        # All at same timestamp = 0 gap => bursty
        records = [
            TrafficRecord(source="a", target="b", timestamp=0.0, latency_ms=5)
            for _ in range(10)
        ]
        analyzer = TrafficAnalyzer(records=records)
        report = analyzer.analyze()
        self.assertEqual(report.pairs[0].pattern, TrafficPattern.BURSTY)


class TestPercentile(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(TrafficAnalyzer._percentile([], 50), 0.0)

    def test_single(self) -> None:
        self.assertEqual(TrafficAnalyzer._percentile([10.0], 99), 10.0)

    def test_basic(self) -> None:
        values = list(range(1, 101))
        p50 = TrafficAnalyzer._percentile([float(v) for v in values], 50)
        self.assertAlmostEqual(p50, 50.5, places=0)


class TestTrafficPattern(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(TrafficPattern.STEADY.value, "steady")
        self.assertEqual(TrafficPattern.BURSTY.value, "bursty")
        self.assertEqual(TrafficPattern.GROWING.value, "growing")


if __name__ == "__main__":
    unittest.main()
