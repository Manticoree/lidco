"""Tests for lidco.budget.session_report."""
from __future__ import annotations

import unittest

from lidco.budget.session_report import SessionReport, SessionReportGenerator


class TestSessionReport(unittest.TestCase):
    def test_defaults(self) -> None:
        r = SessionReport()
        assert r.session_id == ""
        assert r.total_tokens == 0
        assert r.efficiency_score == 0.0
        assert r.recommendations == ()

    def test_frozen(self) -> None:
        r = SessionReport()
        with self.assertRaises(AttributeError):
            r.session_id = "x"  # type: ignore[misc]


class TestSessionReportGenerator(unittest.TestCase):
    def test_generate_basic(self) -> None:
        gen = SessionReportGenerator()
        r = gen.generate(session_id="s1", total=50000, limit=128000)
        assert r.session_id == "s1"
        assert r.total_tokens == 50000
        assert 0.0 <= r.efficiency_score <= 1.0

    def test_efficiency_low_usage(self) -> None:
        gen = SessionReportGenerator()
        r = gen.generate(total=10000, limit=128000)
        assert r.efficiency_score > 0.5

    def test_efficiency_high_usage(self) -> None:
        gen = SessionReportGenerator()
        r = gen.generate(total=120000, limit=128000, peak=120000)
        assert r.efficiency_score < 0.5

    def test_recommendations_high_peak(self) -> None:
        gen = SessionReportGenerator()
        r = gen.generate(total=50000, limit=128000, peak=120000)
        assert any("compaction" in rec.lower() for rec in r.recommendations)

    def test_recommendations_good_efficiency(self) -> None:
        gen = SessionReportGenerator()
        r = gen.generate(total=10000, limit=128000, peak=10000, saved=5000)
        assert any("good" in rec.lower() for rec in r.recommendations)

    def test_format_report(self) -> None:
        gen = SessionReportGenerator()
        r = gen.generate(session_id="demo", total=30000, limit=128000, peak=30000, turns=5)
        text = gen.format_report(r)
        assert "demo" in text
        assert "30,000" in text
        assert "Recommendations:" in text

    def test_export(self) -> None:
        gen = SessionReportGenerator()
        r = gen.generate(session_id="export_test", total=10000, limit=128000)
        data = gen.export(r)
        assert data["session_id"] == "export_test"
        assert data["total_tokens"] == 10000
        assert isinstance(data["recommendations"], list)

    def test_summary(self) -> None:
        gen = SessionReportGenerator()
        gen.generate(session_id="a")
        gen.generate(session_id="b")
        text = gen.summary()
        assert "2" in text

    def test_zero_limit(self) -> None:
        gen = SessionReportGenerator()
        r = gen.generate(total=100, limit=0)
        assert r.efficiency_score == 0.0


if __name__ == "__main__":
    unittest.main()
