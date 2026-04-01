"""Human-readable budget reports."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BudgetReport:
    """Immutable budget report snapshot."""

    total_tokens: int = 0
    tokens_remaining: int = 0
    context_limit: int = 128_000
    utilization: float = 0.0
    compactions: int = 0
    tokens_saved: int = 0
    peak_usage: int = 0
    turns: int = 0
    debt: int = 0


class BudgetReporter:
    """Create and format budget reports."""

    def __init__(self) -> None:
        self._reports: list[BudgetReport] = []

    def create_report(
        self,
        total: int,
        remaining: int,
        limit: int,
        compactions: int = 0,
        saved: int = 0,
        peak: int = 0,
        turns: int = 0,
        debt: int = 0,
    ) -> BudgetReport:
        """Build a BudgetReport and store it."""
        util = total / limit if limit > 0 else 0.0
        report = BudgetReport(
            total_tokens=total,
            tokens_remaining=remaining,
            context_limit=limit,
            utilization=round(util, 4),
            compactions=compactions,
            tokens_saved=saved,
            peak_usage=peak,
            turns=turns,
            debt=debt,
        )
        self._reports = [*self._reports, report]
        return report

    def format_report(self, report: BudgetReport) -> str:
        """Multi-line formatted report with header, bar, breakdown, recommendations."""
        bar = self.format_bar(report.total_tokens, report.context_limit)
        lines = [
            "=== Budget Report ===",
            bar,
            f"Used: {report.total_tokens:,} / {report.context_limit:,}",
            f"Remaining: {report.tokens_remaining:,}",
            f"Utilization: {report.utilization * 100:.1f}%",
            f"Peak: {report.peak_usage:,}",
            f"Turns: {report.turns}",
            f"Compactions: {report.compactions} ({report.tokens_saved:,} saved)",
            f"Debt: {report.debt:,}",
        ]
        score = self.efficiency_score(report)
        if report.utilization > 0.95:
            lines.append("Recommendation: EMERGENCY compaction needed")
        elif report.utilization > 0.85:
            lines.append("Recommendation: Compact soon")
        elif report.utilization > 0.70:
            lines.append("Recommendation: Monitor usage")
        else:
            lines.append("Recommendation: Budget healthy")
        lines.append(f"Efficiency: {score:.2f}")
        return "\n".join(lines)

    def format_bar(self, used: int, total: int, width: int = 40) -> str:
        """Visual bar like: ████████████░░░░░░ 60.2%"""
        if total <= 0:
            return "░" * width + " 0.0%"
        ratio = min(used / total, 1.0)
        filled = int(ratio * width)
        empty = width - filled
        pct = ratio * 100
        return "█" * filled + "░" * empty + f" {pct:.1f}%"

    def efficiency_score(self, report: BudgetReport) -> float:
        """0.0-1.0 based on tokens saved relative to total used."""
        if report.total_tokens <= 0:
            return 1.0
        return min(1.0, report.tokens_saved / report.total_tokens) if report.tokens_saved > 0 else 0.0

    def export_json(self, report: BudgetReport) -> dict:
        """Export report as a JSON-serializable dict."""
        return {
            "total_tokens": report.total_tokens,
            "tokens_remaining": report.tokens_remaining,
            "context_limit": report.context_limit,
            "utilization": report.utilization,
            "compactions": report.compactions,
            "tokens_saved": report.tokens_saved,
            "peak_usage": report.peak_usage,
            "turns": report.turns,
            "debt": report.debt,
        }

    def summary(self) -> str:
        """Summary of all reports generated."""
        if not self._reports:
            return "BudgetReporter: no reports generated."
        last = self._reports[-1]
        return (
            f"BudgetReporter: {len(self._reports)} reports, "
            f"latest={last.total_tokens:,}/{last.context_limit:,} "
            f"({last.utilization * 100:.1f}%)"
        )
