"""Tests for lidco.logintel.anomaly — Log Anomaly Detector."""

from __future__ import annotations

import unittest

from lidco.logintel.anomaly import (
    Anomaly,
    AnomalyReport,
    AnomalyType,
    Baseline,
    LogAnomalyDetector,
)
from lidco.logintel.parser import LogEntry, LogFormat


def _entry(level: str = "INFO", msg: str = "ok", source: str = "api", ts: str = "t1") -> LogEntry:
    return LogEntry(timestamp=ts, level=level, message=msg, source=source, format=LogFormat.JSON)


class TestAnomalyType(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(AnomalyType.VOLUME_SPIKE.value, "volume_spike")
        self.assertEqual(AnomalyType.NEW_ERROR.value, "new_error")
        self.assertEqual(AnomalyType.LEVEL_SHIFT.value, "level_shift")
        self.assertEqual(AnomalyType.MISSING_SERVICE.value, "missing_service")


class TestBaseline(unittest.TestCase):
    def test_is_empty(self) -> None:
        self.assertTrue(Baseline().is_empty)

    def test_not_empty(self) -> None:
        b = Baseline(avg_volume=10.0)
        self.assertFalse(b.is_empty)


class TestAnomalyReport(unittest.TestCase):
    def test_count(self) -> None:
        r = AnomalyReport()
        self.assertEqual(r.count, 0)

    def test_max_score_empty(self) -> None:
        self.assertEqual(AnomalyReport().max_score, 0.0)

    def test_max_score(self) -> None:
        a1 = Anomaly(anomaly_type=AnomalyType.NEW_ERROR, description="a", score=0.5)
        a2 = Anomaly(anomaly_type=AnomalyType.NEW_ERROR, description="b", score=0.9)
        r = AnomalyReport(anomalies=[a1, a2])
        self.assertAlmostEqual(r.max_score, 0.9)

    def test_by_type(self) -> None:
        a1 = Anomaly(anomaly_type=AnomalyType.NEW_ERROR, description="a", score=0.8)
        a2 = Anomaly(anomaly_type=AnomalyType.VOLUME_SPIKE, description="b", score=0.5)
        r = AnomalyReport(anomalies=[a1, a2])
        self.assertEqual(len(r.by_type(AnomalyType.NEW_ERROR)), 1)
        self.assertEqual(len(r.by_type(AnomalyType.MISSING_SERVICE)), 0)


class TestLogAnomalyDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = LogAnomalyDetector()

    # -- Baseline ----------------------------------------------------------

    def test_build_baseline_empty(self) -> None:
        b = self.detector.build_baseline([])
        self.assertTrue(b.is_empty)

    def test_build_baseline(self) -> None:
        entries = [_entry("INFO", "ok", "api"), _entry("ERROR", "fail", "db")]
        b = self.detector.build_baseline(entries)
        self.assertEqual(b.avg_volume, 2.0)
        self.assertIn("fail", b.known_errors)
        self.assertIn("api", b.known_services)
        self.assertIn("db", b.known_services)
        self.assertIn("INFO", b.level_distribution)

    def test_set_baseline(self) -> None:
        b = Baseline(avg_volume=100.0)
        self.detector.set_baseline(b)
        self.assertEqual(self.detector.baseline.avg_volume, 100.0)

    # -- Detection: no baseline --------------------------------------------

    def test_detect_no_baseline(self) -> None:
        entries = [_entry("ERROR", "boom")]
        report = self.detector.detect(entries)
        self.assertEqual(report.total_entries, 1)
        # With no baseline, new_error still fires (empty known_errors set)
        new_errors = report.by_type(AnomalyType.NEW_ERROR)
        self.assertEqual(len(new_errors), 1)

    # -- Detection: new error type -----------------------------------------

    def test_detect_new_error(self) -> None:
        baseline = Baseline(known_errors={"old error"})
        self.detector.set_baseline(baseline)
        entries = [_entry("ERROR", "brand new error")]
        report = self.detector.detect(entries)
        new_errors = report.by_type(AnomalyType.NEW_ERROR)
        self.assertEqual(len(new_errors), 1)
        self.assertIn("brand new error", new_errors[0].description)

    def test_detect_known_error_not_flagged(self) -> None:
        baseline = Baseline(known_errors={"known error"})
        self.detector.set_baseline(baseline)
        entries = [_entry("ERROR", "known error")]
        report = self.detector.detect(entries)
        new_errors = report.by_type(AnomalyType.NEW_ERROR)
        self.assertEqual(len(new_errors), 0)

    def test_detect_deduplicates_new_errors(self) -> None:
        entries = [_entry("ERROR", "same error"), _entry("ERROR", "same error")]
        report = self.detector.detect(entries)
        new_errors = report.by_type(AnomalyType.NEW_ERROR)
        self.assertEqual(len(new_errors), 1)

    # -- Detection: volume spike -------------------------------------------

    def test_detect_volume_spike(self) -> None:
        baseline = Baseline(avg_volume=10.0, std_volume=2.0)
        self.detector.set_baseline(baseline)
        # 20 entries with baseline avg 10 => z=5 >> threshold
        entries = [_entry() for _ in range(20)]
        report = self.detector.detect(entries)
        spikes = report.by_type(AnomalyType.VOLUME_SPIKE)
        self.assertEqual(len(spikes), 1)

    def test_no_volume_spike_within_range(self) -> None:
        baseline = Baseline(avg_volume=10.0, std_volume=5.0)
        self.detector.set_baseline(baseline)
        entries = [_entry() for _ in range(12)]
        report = self.detector.detect(entries)
        spikes = report.by_type(AnomalyType.VOLUME_SPIKE)
        self.assertEqual(len(spikes), 0)

    # -- Detection: level shift --------------------------------------------

    def test_detect_level_shift(self) -> None:
        baseline = Baseline(level_distribution={"INFO": 0.9, "ERROR": 0.1})
        self.detector.set_baseline(baseline)
        # All errors = 100% error rate, baseline was 10%
        entries = [_entry("ERROR", f"err{i}") for i in range(10)]
        report = self.detector.detect(entries)
        shifts = report.by_type(AnomalyType.LEVEL_SHIFT)
        self.assertGreaterEqual(len(shifts), 1)

    def test_no_level_shift(self) -> None:
        baseline = Baseline(level_distribution={"INFO": 0.5, "ERROR": 0.5})
        self.detector.set_baseline(baseline)
        entries = [_entry("ERROR", "e"), _entry("INFO", "i")]
        report = self.detector.detect(entries)
        shifts = report.by_type(AnomalyType.LEVEL_SHIFT)
        self.assertEqual(len(shifts), 0)

    # -- Detection: missing service ----------------------------------------

    def test_detect_missing_service(self) -> None:
        baseline = Baseline(known_services={"api", "db", "cache"})
        self.detector.set_baseline(baseline)
        entries = [_entry(source="api")]
        report = self.detector.detect(entries)
        missing = report.by_type(AnomalyType.MISSING_SERVICE)
        names = {a.metadata["service"] for a in missing}
        self.assertIn("db", names)
        self.assertIn("cache", names)

    def test_no_missing_service(self) -> None:
        baseline = Baseline(known_services={"api"})
        self.detector.set_baseline(baseline)
        entries = [_entry(source="api")]
        report = self.detector.detect(entries)
        missing = report.by_type(AnomalyType.MISSING_SERVICE)
        self.assertEqual(len(missing), 0)

    # -- Score threshold ---------------------------------------------------

    def test_score_threshold_filters(self) -> None:
        detector = LogAnomalyDetector(score_threshold=0.9)
        # New errors have score=0.8, should be filtered out
        baseline = Baseline(known_errors=set())
        detector.set_baseline(baseline)
        entries = [_entry("ERROR", "something")]
        report = detector.detect(entries)
        self.assertEqual(report.count, 0)


if __name__ == "__main__":
    unittest.main()
