"""
Flaky test dashboard — reporting and metrics.

Top flakers, trends, MTTR, quarantine status, team breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from lidco.flaky.detector import FlakyTestResult, FlakySeverity, TestRun
from lidco.flaky.quarantine import FlakyQuarantine, QuarantineStatus


@dataclass(frozen=True)
class FlakeEntry:
    """Single entry in the top-flakers list."""

    test_name: str
    fail_count: int
    total_runs: int
    pass_rate: float
    severity: str
    quarantine_status: str = "none"
    team: str = ""


@dataclass(frozen=True)
class TrendPoint:
    """A single trend data point."""

    period: str
    flaky_count: int
    total_tests: int
    flaky_rate: float


@dataclass(frozen=True)
class DashboardReport:
    """Full dashboard output."""

    total_tests: int
    flaky_count: int
    flaky_rate: float
    top_flakers: list[FlakeEntry] = field(default_factory=list)
    trends: list[TrendPoint] = field(default_factory=list)
    mean_time_to_resolve_hours: float = 0.0
    quarantine_active: int = 0
    quarantine_released: int = 0
    team_breakdown: dict[str, int] = field(default_factory=dict)
    severity_breakdown: dict[str, int] = field(default_factory=dict)


class FlakyDashboard:
    """Generate flaky test dashboard reports.

    Parameters
    ----------
    quarantine : FlakyQuarantine | None
        Optional quarantine instance for status overlay.
    team_mapping : dict[str, str] | None
        Map test_name prefix to team name.
    """

    def __init__(
        self,
        *,
        quarantine: FlakyQuarantine | None = None,
        team_mapping: dict[str, str] | None = None,
    ) -> None:
        self._quarantine = quarantine
        self._team_mapping = team_mapping or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        results: Sequence[FlakyTestResult],
        *,
        top_n: int = 10,
        history: Sequence[tuple[str, int, int]] | None = None,
    ) -> DashboardReport:
        """Build a dashboard report from detection results.

        Parameters
        ----------
        results : sequence of FlakyTestResult
        top_n : int
            Number of top flakers to include.
        history : sequence of (period, flaky_count, total_tests)
            Optional trend history.
        """
        flaky = [r for r in results if r.is_flaky]
        total = len(results)
        flaky_count = len(flaky)
        flaky_rate = flaky_count / total if total else 0.0

        # Top flakers sorted by fail_count descending
        sorted_flaky = sorted(flaky, key=lambda r: r.fail_count, reverse=True)
        top_flakers = [self._to_flake_entry(r) for r in sorted_flaky[:top_n]]

        # Trends
        trends: list[TrendPoint] = []
        if history:
            for period, fc, tt in history:
                trends.append(
                    TrendPoint(
                        period=period,
                        flaky_count=fc,
                        total_tests=tt,
                        flaky_rate=fc / tt if tt else 0.0,
                    )
                )

        # Quarantine stats
        q_active = 0
        q_released = 0
        if self._quarantine:
            s = self._quarantine.summary()
            q_active = s.active
            q_released = s.released

        # Team breakdown
        team_breakdown: dict[str, int] = {}
        for r in flaky:
            team = self._resolve_team(r.test_name)
            team_breakdown[team] = team_breakdown.get(team, 0) + 1

        # Severity breakdown
        severity_breakdown: dict[str, int] = {}
        for r in flaky:
            key = r.severity.value
            severity_breakdown[key] = severity_breakdown.get(key, 0) + 1

        return DashboardReport(
            total_tests=total,
            flaky_count=flaky_count,
            flaky_rate=flaky_rate,
            top_flakers=top_flakers,
            trends=trends,
            mean_time_to_resolve_hours=0.0,  # placeholder for real MTTR calc
            quarantine_active=q_active,
            quarantine_released=q_released,
            team_breakdown=team_breakdown,
            severity_breakdown=severity_breakdown,
        )

    def format_text(self, report: DashboardReport) -> str:
        """Render a dashboard report as plain text."""
        lines = [
            "Flaky Test Dashboard",
            "=" * 40,
            f"Total tests: {report.total_tests}",
            f"Flaky tests: {report.flaky_count} ({report.flaky_rate:.1%})",
            f"Quarantine: {report.quarantine_active} active, {report.quarantine_released} released",
            "",
        ]

        if report.top_flakers:
            lines.append("Top Flakers:")
            for i, f in enumerate(report.top_flakers, 1):
                lines.append(
                    f"  {i}. {f.test_name} — "
                    f"{f.fail_count}/{f.total_runs} fails, "
                    f"pass_rate={f.pass_rate:.1%}, "
                    f"severity={f.severity}"
                )

        if report.trends:
            lines.append("")
            lines.append("Trends:")
            for t in report.trends:
                lines.append(
                    f"  {t.period}: {t.flaky_count}/{t.total_tests} flaky ({t.flaky_rate:.1%})"
                )

        if report.team_breakdown:
            lines.append("")
            lines.append("Team Breakdown:")
            for team, count in sorted(
                report.team_breakdown.items(), key=lambda kv: kv[1], reverse=True
            ):
                lines.append(f"  {team}: {count}")

        if report.severity_breakdown:
            lines.append("")
            lines.append("Severity Breakdown:")
            for sev, count in sorted(report.severity_breakdown.items()):
                lines.append(f"  {sev}: {count}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _to_flake_entry(self, result: FlakyTestResult) -> FlakeEntry:
        q_status = "none"
        if self._quarantine:
            entry = self._quarantine.get_entry(result.test_name)
            if entry is not None:
                q_status = entry.status.value
        return FlakeEntry(
            test_name=result.test_name,
            fail_count=result.fail_count,
            total_runs=result.total_runs,
            pass_rate=result.pass_rate,
            severity=result.severity.value,
            quarantine_status=q_status,
            team=self._resolve_team(result.test_name),
        )

    def _resolve_team(self, test_name: str) -> str:
        for prefix, team in self._team_mapping.items():
            if test_name.startswith(prefix):
                return team
        return "unassigned"
