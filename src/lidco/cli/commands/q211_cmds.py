"""Q211 CLI commands: /health-score, /tech-debt, /complexity, /churn."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q211 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /health-score
    # ------------------------------------------------------------------

    async def health_score_handler(args: str) -> str:
        from lidco.project_analytics.health_scorer import HealthScorer

        scorer = HealthScorer()
        path = args.strip() or "."
        scorer.set_project(path)
        # Add default dimensions as a demo
        scorer.add_dimension("structure", 75, weight=1.0, detail="Project structure")
        scorer.add_dimension("docs", 60, weight=0.5, detail="Documentation coverage")
        report = scorer.compute()
        grade = scorer.grade()
        lines = [
            f"Health score: {report.overall_score:.1f}/100 (grade: {grade})",
            f"Project: {report.project_path}",
        ]
        for dim in report.dimensions:
            lines.append(f"  {dim.name}: {dim.score:.0f} (weight {dim.weight})")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /tech-debt
    # ------------------------------------------------------------------

    async def tech_debt_handler(args: str) -> str:
        from lidco.project_analytics.debt_tracker import TechDebtTracker
        import os

        path = args.strip() or "."
        tracker = TechDebtTracker()

        if os.path.isfile(path):
            tracker.scan_file(path)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for fname in files:
                    if fname.endswith(".py"):
                        try:
                            tracker.scan_file(os.path.join(root, fname))
                        except Exception:
                            pass

        report = tracker.report()
        lines = [
            f"Debt items: {len(report.items)}",
            f"Estimated hours: {report.total_hours}",
        ]
        for sev, count in sorted(report.by_severity.items()):
            lines.append(f"  {sev}: {count}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /complexity
    # ------------------------------------------------------------------

    async def complexity_handler(args: str) -> str:
        from lidco.project_analytics.complexity_analyzer import ComplexityAnalyzer

        path = args.strip()
        if not path:
            return "Usage: /complexity <file>"

        analyzer = ComplexityAnalyzer()
        with open(path, encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        results = analyzer.analyze_module(source, file=path)
        summary = analyzer.summary(results)
        lines = [summary]
        for r in results[:10]:
            lines.append(f"  {r.name}: CC={r.cyclomatic} MI={r.maintainability:.1f}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /churn
    # ------------------------------------------------------------------

    async def churn_handler(args: str) -> str:
        from lidco.project_analytics.churn_analyzer import ChurnAnalyzer

        analyzer = ChurnAnalyzer()
        # Without actual git log, return a placeholder summary
        return analyzer.summary()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(SlashCommand("health-score", "Compute codebase health score", health_score_handler))
    registry.register(SlashCommand("tech-debt", "Scan for technical debt markers", tech_debt_handler))
    registry.register(SlashCommand("complexity", "Analyze code complexity", complexity_handler))
    registry.register(SlashCommand("churn", "Show file change frequency", churn_handler))
