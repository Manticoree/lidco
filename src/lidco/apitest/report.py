"""API Test Report — task 1695.

Generate API test reports with pass/fail, response times,
validation errors, and baseline comparison.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from lidco.apitest.runner import SuiteResult, TestCaseResult


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BaselineEntry:
    """Baseline performance data for a single test case."""

    name: str
    avg_duration_ms: float
    expected_status: int = 200


@dataclass(frozen=True)
class Baseline:
    """Collection of baseline entries for comparison."""

    entries: dict[str, BaselineEntry] = field(default_factory=dict)

    def get(self, name: str) -> BaselineEntry | None:
        return self.entries.get(name)


# ---------------------------------------------------------------------------
# Report data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CaseReport:
    """Report for a single test case."""

    name: str
    passed: bool
    status_code: int
    duration_ms: float
    error: str
    assertion_failures: tuple[str, ...] = ()
    baseline_diff_ms: float | None = None
    baseline_status_match: bool | None = None


@dataclass(frozen=True)
class SuiteReport:
    """Full report for a test suite run."""

    name: str
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    cases: tuple[CaseReport, ...] = ()


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

class ApiTestReporter:
    """Build reports from *SuiteResult* data."""

    def __init__(self, baseline: Baseline | None = None) -> None:
        self._baseline = baseline or Baseline()

    def build_report(self, result: SuiteResult) -> SuiteReport:
        """Build a *SuiteReport* from a *SuiteResult*."""
        case_reports: list[CaseReport] = []
        durations: list[float] = []

        for cr in result.results:
            failures = self._collect_failures(cr)
            bl = self._baseline.get(cr.name)
            bl_diff: float | None = None
            bl_status: bool | None = None
            if bl is not None:
                bl_diff = round(cr.duration_ms - bl.avg_duration_ms, 2)
                bl_status = cr.status_code == bl.expected_status

            case_reports.append(CaseReport(
                name=cr.name,
                passed=cr.passed,
                status_code=cr.status_code,
                duration_ms=cr.duration_ms,
                error=cr.error,
                assertion_failures=tuple(failures),
                baseline_diff_ms=bl_diff,
                baseline_status_match=bl_status,
            ))
            durations.append(cr.duration_ms)

        avg_d = sum(durations) / len(durations) if durations else 0.0
        min_d = min(durations) if durations else 0.0
        max_d = max(durations) if durations else 0.0

        return SuiteReport(
            name=result.name,
            passed=result.passed,
            total=result.total,
            passed_count=result.passed_count,
            failed_count=result.failed_count,
            duration_ms=result.duration_ms,
            avg_duration_ms=round(avg_d, 2),
            min_duration_ms=round(min_d, 2),
            max_duration_ms=round(max_d, 2),
            cases=tuple(case_reports),
        )

    def format_text(self, report: SuiteReport) -> str:
        """Format the report as human-readable text."""
        lines: list[str] = [
            f"API Test Report: {report.name}",
            f"{'=' * 50}",
            f"Result: {'PASS' if report.passed else 'FAIL'}",
            f"Total: {report.total}  Passed: {report.passed_count}  Failed: {report.failed_count}",
            f"Duration: {report.duration_ms}ms  "
            f"(avg={report.avg_duration_ms}ms, "
            f"min={report.min_duration_ms}ms, "
            f"max={report.max_duration_ms}ms)",
            "",
        ]

        for cr in report.cases:
            status = "PASS" if cr.passed else "FAIL"
            lines.append(f"  [{status}] {cr.name} — {cr.status_code} ({cr.duration_ms}ms)")
            if cr.error:
                lines.append(f"         Error: {cr.error}")
            for fail in cr.assertion_failures:
                lines.append(f"         Assertion: {fail}")
            if cr.baseline_diff_ms is not None:
                sign = "+" if cr.baseline_diff_ms >= 0 else ""
                lines.append(f"         Baseline diff: {sign}{cr.baseline_diff_ms}ms")
            if cr.baseline_status_match is not None and not cr.baseline_status_match:
                lines.append("         Baseline status MISMATCH")

        return "\n".join(lines)

    def format_json(self, report: SuiteReport) -> str:
        """Format the report as JSON string."""
        return json.dumps(self._report_to_dict(report), indent=2)

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _collect_failures(cr: TestCaseResult) -> list[str]:
        failures: list[str] = []
        for ar in cr.assertion_results:
            if not ar.passed:
                msg = (
                    f"{ar.assertion.field} {ar.assertion.operator} "
                    f"{ar.assertion.expected!r}: got {ar.actual!r}"
                )
                if ar.error:
                    msg += f" ({ar.error})"
                failures.append(msg)
        return failures

    @staticmethod
    def _report_to_dict(report: SuiteReport) -> dict[str, Any]:
        cases = []
        for c in report.cases:
            cases.append({
                "name": c.name,
                "passed": c.passed,
                "status_code": c.status_code,
                "duration_ms": c.duration_ms,
                "error": c.error,
                "assertion_failures": list(c.assertion_failures),
                "baseline_diff_ms": c.baseline_diff_ms,
                "baseline_status_match": c.baseline_status_match,
            })
        return {
            "name": report.name,
            "passed": report.passed,
            "total": report.total,
            "passed_count": report.passed_count,
            "failed_count": report.failed_count,
            "duration_ms": report.duration_ms,
            "avg_duration_ms": report.avg_duration_ms,
            "min_duration_ms": report.min_duration_ms,
            "max_duration_ms": report.max_duration_ms,
            "cases": cases,
        }
