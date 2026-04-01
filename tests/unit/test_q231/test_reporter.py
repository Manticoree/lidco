"""Tests for lidco.budget.reporter."""
from __future__ import annotations

import pytest

from lidco.budget.reporter import BudgetReport, BudgetReporter


class TestBudgetReport:
    def test_frozen(self) -> None:
        r = BudgetReport()
        with pytest.raises(AttributeError):
            r.total_tokens = 1  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = BudgetReport()
        assert r.total_tokens == 0
        assert r.context_limit == 128_000
        assert r.utilization == 0.0
        assert r.debt == 0


class TestBudgetReporter:
    def test_create_report(self) -> None:
        rep = BudgetReporter()
        r = rep.create_report(total=50_000, remaining=78_000, limit=128_000)
        assert r.total_tokens == 50_000
        assert r.tokens_remaining == 78_000
        assert r.utilization == pytest.approx(0.3906, abs=0.001)

    def test_format_report_contains_sections(self) -> None:
        rep = BudgetReporter()
        r = rep.create_report(total=100_000, remaining=28_000, limit=128_000, turns=5)
        text = rep.format_report(r)
        assert "Budget Report" in text
        assert "100,000" in text
        assert "Turns: 5" in text

    def test_format_bar_empty(self) -> None:
        rep = BudgetReporter()
        bar = rep.format_bar(0, 100, width=10)
        assert "0.0%" in bar
        assert "░" * 10 in bar

    def test_format_bar_full(self) -> None:
        rep = BudgetReporter()
        bar = rep.format_bar(100, 100, width=10)
        assert "100.0%" in bar
        assert "█" * 10 in bar

    def test_format_bar_partial(self) -> None:
        rep = BudgetReporter()
        bar = rep.format_bar(50, 100, width=20)
        assert "50.0%" in bar

    def test_efficiency_score_no_savings(self) -> None:
        rep = BudgetReporter()
        r = BudgetReport(total_tokens=1000, tokens_saved=0)
        assert rep.efficiency_score(r) == 0.0

    def test_efficiency_score_with_savings(self) -> None:
        rep = BudgetReporter()
        r = BudgetReport(total_tokens=1000, tokens_saved=500)
        assert rep.efficiency_score(r) == 0.5

    def test_efficiency_score_zero_total(self) -> None:
        rep = BudgetReporter()
        r = BudgetReport(total_tokens=0)
        assert rep.efficiency_score(r) == 1.0

    def test_export_json(self) -> None:
        rep = BudgetReporter()
        r = rep.create_report(total=10, remaining=90, limit=100, debt=5)
        d = rep.export_json(r)
        assert d["total_tokens"] == 10
        assert d["debt"] == 5
        assert len(d) == 9

    def test_summary_no_reports(self) -> None:
        rep = BudgetReporter()
        assert "no reports" in rep.summary()

    def test_summary_with_reports(self) -> None:
        rep = BudgetReporter()
        rep.create_report(total=50, remaining=50, limit=100)
        s = rep.summary()
        assert "1 reports" in s
