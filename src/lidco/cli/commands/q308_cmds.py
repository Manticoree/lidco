"""
Q308 CLI commands — /contributions, /velocity, /predict-churn, /repo-health

Registered via register_q308_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q308_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q308 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /contributions — Per-author contribution analytics
    # ------------------------------------------------------------------
    async def contributions_handler(args: str) -> str:
        """
        Usage: /contributions [--since YYYY-MM-DD] [--top N] [path]
        """
        from lidco.gitanalytics.contributions import ContributionAnalyzer

        parts = shlex.split(args) if args.strip() else []
        since: str | None = None
        top_n = 10
        repo = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--since" and i + 1 < len(parts):
                since = parts[i + 1]
                i += 2
            elif parts[i] == "--top" and i + 1 < len(parts):
                try:
                    top_n = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                repo = parts[i]
                i += 1

        analyzer = ContributionAnalyzer(repo)
        summary = analyzer.analyze(since=since)

        lines = [
            f"Contributions: {summary.total_commits} commits by {summary.total_authors} author(s)",
            f"Period: {summary.period_start} .. {summary.period_end}",
            "",
        ]
        for a in summary.authors[:top_n]:
            lines.append(
                f"  {a.name} <{a.email}>: "
                f"{a.commits} commits, "
                f"+{a.lines_added}/-{a.lines_removed}, "
                f"{a.files_touched} files"
            )

        return "\n".join(lines)

    registry.register_async(
        "contributions",
        "Per-author contribution analytics",
        contributions_handler,
    )

    # ------------------------------------------------------------------
    # /velocity — Team velocity metrics
    # ------------------------------------------------------------------
    async def velocity_handler(args: str) -> str:
        """
        Usage: /velocity [--days N] [path]
        """
        from lidco.gitanalytics.velocity import VelocityAnalyzer

        parts = shlex.split(args) if args.strip() else []
        days = 30
        repo = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--days" and i + 1 < len(parts):
                try:
                    days = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                repo = parts[i]
                i += 1

        analyzer = VelocityAnalyzer(repo)
        metrics = analyzer.compute(days=days)

        return (
            f"Velocity ({metrics.period_days}d):\n"
            f"  Total commits: {metrics.total_commits}\n"
            f"  Commits/day: {metrics.commits_per_day}\n"
            f"  Active days: {metrics.active_days}\n"
            f"  Active authors: {metrics.authors_active}\n"
            f"  Avg commits/author: {metrics.avg_commits_per_author}\n"
            f"  Busiest day: {metrics.busiest_day} ({metrics.busiest_day_commits} commits)"
        )

    registry.register_async(
        "velocity",
        "Team velocity metrics",
        velocity_handler,
    )

    # ------------------------------------------------------------------
    # /predict-churn — Predict files likely to change
    # ------------------------------------------------------------------
    async def predict_churn_handler(args: str) -> str:
        """
        Usage: /predict-churn [--days N] [--top N] [path]
        """
        from lidco.gitanalytics.churn_predictor import ChurnPredictor

        parts = shlex.split(args) if args.strip() else []
        days = 90
        top_n = 20
        repo = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--days" and i + 1 < len(parts):
                try:
                    days = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--top" and i + 1 < len(parts):
                try:
                    top_n = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                repo = parts[i]
                i += 1

        predictor = ChurnPredictor(repo)
        report = predictor.predict(days=days, top_n=top_n)

        if not report.files:
            return f"No churn data found in the last {days} days."

        lines = [
            f"Churn prediction ({report.period_days}d, {report.total_files_analyzed} files analysed):",
        ]
        for f in report.files:
            coupled = ""
            if f.coupled_files:
                coupled = f" [coupled: {', '.join(f.coupled_files[:3])}]"
            lines.append(
                f"  {f.path}: score={f.score}, changes={f.change_count}{coupled}"
            )

        return "\n".join(lines)

    registry.register_async(
        "predict-churn",
        "Predict files likely to change based on history",
        predict_churn_handler,
    )

    # ------------------------------------------------------------------
    # /repo-health — Overall repository health score
    # ------------------------------------------------------------------
    async def repo_health_handler(args: str) -> str:
        """
        Usage: /repo-health [--days N] [path]
        """
        from lidco.gitanalytics.health import HealthAnalyzer

        parts = shlex.split(args) if args.strip() else []
        days = 30
        repo = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--days" and i + 1 < len(parts):
                try:
                    days = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                repo = parts[i]
                i += 1

        analyzer = HealthAnalyzer(repo)
        report = analyzer.analyze(days=days)

        lines = [
            f"Repository Health: {report.grade} ({report.overall_score})",
            "",
        ]
        for d in report.dimensions:
            lines.append(f"  {d.name}: {d.score} — {d.detail}")

        if report.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for r in report.recommendations:
                lines.append(f"  - {r}")

        return "\n".join(lines)

    registry.register_async(
        "repo-health",
        "Overall repository health score",
        repo_health_handler,
    )
