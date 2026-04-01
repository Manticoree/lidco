"""End-of-session budget report with efficiency analysis."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionReport:
    """Immutable end-of-session budget report."""

    session_id: str = ""
    total_tokens: int = 0
    context_limit: int = 128000
    peak_usage: int = 0
    turns: int = 0
    compactions: int = 0
    tokens_saved: int = 0
    debt_incurred: int = 0
    debt_repaid: int = 0
    efficiency_score: float = 0.0
    recommendations: tuple[str, ...] = ()


class SessionReportGenerator:
    """Generate end-of-session budget reports."""

    def __init__(self) -> None:
        self._reports: list[SessionReport] = []

    def generate(
        self,
        session_id: str = "",
        total: int = 0,
        limit: int = 128000,
        peak: int = 0,
        turns: int = 0,
        compactions: int = 0,
        saved: int = 0,
        debt_incurred: int = 0,
        debt_repaid: int = 0,
    ) -> SessionReport:
        """Build a :class:`SessionReport` with computed metrics."""
        efficiency = self._compute_efficiency(total, limit, saved)
        report_data = {
            "total": total,
            "limit": limit,
            "peak": peak,
            "turns": turns,
            "compactions": compactions,
            "saved": saved,
            "efficiency": efficiency,
        }
        recs = tuple(self._generate_recommendations(report_data))
        report = SessionReport(
            session_id=session_id,
            total_tokens=total,
            context_limit=limit,
            peak_usage=peak,
            turns=turns,
            compactions=compactions,
            tokens_saved=saved,
            debt_incurred=debt_incurred,
            debt_repaid=debt_repaid,
            efficiency_score=efficiency,
            recommendations=recs,
        )
        self._reports = [*self._reports, report]
        return report

    def _compute_efficiency(self, total: int, limit: int, saved: int) -> float:
        """Return 0.0–1.0 efficiency score; higher is more efficient."""
        if limit <= 0:
            return 0.0
        utilization = total / limit
        savings_bonus = min(0.2, saved / limit) if limit > 0 else 0.0
        raw = max(0.0, 1.0 - utilization) + savings_bonus
        return round(min(1.0, max(0.0, raw)), 4)

    def _generate_recommendations(self, report_data: dict) -> list[str]:
        """Produce human-readable recommendations."""
        recs: list[str] = []
        limit = report_data.get("limit", 1)
        peak = report_data.get("peak", 0)
        efficiency = report_data.get("efficiency", 0.0)
        compactions = report_data.get("compactions", 0)

        if limit > 0 and peak / limit > 0.9:
            recs.append("Consider more aggressive compaction")
        if efficiency > 0.7:
            recs.append("Good budget management")
        if compactions == 0 and peak / max(limit, 1) > 0.5:
            recs.append("Enable compaction to extend session life")
        if not recs:
            recs.append("Session completed within budget")
        return recs

    def format_report(self, report: SessionReport) -> str:
        """Multi-line formatted report."""
        lines = [
            f"Session: {report.session_id or '(unnamed)'}",
            f"Total tokens: {report.total_tokens:,}",
            f"Context limit: {report.context_limit:,}",
            f"Peak usage: {report.peak_usage:,}",
            f"Turns: {report.turns}",
            f"Compactions: {report.compactions}",
            f"Tokens saved: {report.tokens_saved:,}",
            f"Debt incurred: {report.debt_incurred:,}",
            f"Debt repaid: {report.debt_repaid:,}",
            f"Efficiency: {report.efficiency_score:.2%}",
            "Recommendations:",
        ]
        for r in report.recommendations:
            lines.append(f"  - {r}")
        return "\n".join(lines)

    def export(self, report: SessionReport) -> dict:
        """Export *report* as a plain dict."""
        return {
            "session_id": report.session_id,
            "total_tokens": report.total_tokens,
            "context_limit": report.context_limit,
            "peak_usage": report.peak_usage,
            "turns": report.turns,
            "compactions": report.compactions,
            "tokens_saved": report.tokens_saved,
            "debt_incurred": report.debt_incurred,
            "debt_repaid": report.debt_repaid,
            "efficiency_score": report.efficiency_score,
            "recommendations": list(report.recommendations),
        }

    def summary(self) -> str:
        """Summary of generated reports."""
        lines = [f"Reports generated: {len(self._reports)}"]
        for r in self._reports[-5:]:
            lines.append(f"  {r.session_id}: efficiency={r.efficiency_score:.2%}")
        return "\n".join(lines)
