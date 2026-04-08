"""
Q315 CLI commands — /coverage-collect, /coverage-analyze, /coverage-report,
/coverage-optimize

Registered via register_q315_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q315_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q315 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /coverage-collect — Collect coverage data from JSON report
    # ------------------------------------------------------------------
    async def coverage_collect_handler(args: str) -> str:
        """
        Usage: /coverage-collect <json-path> [--compare <json-path>]
        """
        from lidco.coverage.collector import CoverageCollector

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /coverage-collect <json-path> [--compare <json-path>]"

        json_path = parts[0]
        compare_path: str | None = None

        i = 1
        while i < len(parts):
            if parts[i] == "--compare" and i + 1 < len(parts):
                compare_path = parts[i + 1]
                i += 2
            else:
                i += 1

        collector = CoverageCollector()
        snapshot = collector.collect_from_json(json_path)

        lines = [
            f"Collected coverage from {json_path}",
            f"  Files: {len(snapshot.files)}",
            f"  Total lines: {snapshot.total_lines}",
            f"  Covered lines: {snapshot.covered_lines}",
            f"  Line rate: {snapshot.line_rate:.1%}",
        ]

        if compare_path:
            before = collector.collect_from_json(compare_path)
            delta = collector.delta(before, snapshot)
            lines.append("")
            lines.append("Delta:")
            lines.append(f"  Line rate change: {delta.line_rate_delta:+.1%}")
            lines.append(f"  Lines added: {delta.lines_added}")
            lines.append(f"  New files: {len(delta.new_files)}")
            lines.append(f"  Removed files: {len(delta.removed_files)}")

        return "\n".join(lines)

    registry.register_async(
        "coverage-collect",
        "Collect coverage data from a JSON report",
        coverage_collect_handler,
    )

    # ------------------------------------------------------------------
    # /coverage-analyze — Analyze coverage gaps and risk
    # ------------------------------------------------------------------
    async def coverage_analyze_handler(args: str) -> str:
        """
        Usage: /coverage-analyze <json-path>
        """
        from lidco.coverage.analyzer import CoverageAnalyzer
        from lidco.coverage.collector import CoverageCollector

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /coverage-analyze <json-path>"

        json_path = parts[0]
        collector = CoverageCollector()
        snapshot = collector.collect_from_json(json_path)

        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snapshot)

        lines = [
            f"Coverage Analysis ({len(result.file_assessments)} files):",
            f"  Overall risk: {result.overall_risk}",
            f"  Line rate: {result.overall_line_rate:.1%}",
            f"  Function rate: {result.overall_function_rate:.1%}",
            f"  Branch rate: {result.overall_branch_rate:.1%}",
            f"  Uncovered functions: {len(result.uncovered_functions)}",
            f"  Coverage gaps: {len(result.gaps)}",
            f"  Partial branches: {len(result.partial_branches)}",
        ]

        if result.uncovered_functions:
            lines.append("")
            lines.append("Top uncovered functions:")
            for uf in result.uncovered_functions[:10]:
                lines.append(f"  {uf.file_path}:{uf.start_line} {uf.name} [{uf.risk}]")

        return "\n".join(lines)

    registry.register_async(
        "coverage-analyze",
        "Analyze coverage gaps and risk",
        coverage_analyze_handler,
    )

    # ------------------------------------------------------------------
    # /coverage-report — Generate coverage report
    # ------------------------------------------------------------------
    async def coverage_report_handler(args: str) -> str:
        """
        Usage: /coverage-report <json-path> [--format text|json|html]
        """
        from lidco.coverage.analyzer import CoverageAnalyzer
        from lidco.coverage.collector import CoverageCollector
        from lidco.coverage.reporter import CoverageReporter

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /coverage-report <json-path> [--format text|json|html]"

        json_path = parts[0]
        fmt = "text"

        i = 1
        while i < len(parts):
            if parts[i] == "--format" and i + 1 < len(parts):
                fmt = parts[i + 1]
                i += 2
            else:
                i += 1

        collector = CoverageCollector()
        snapshot = collector.collect_from_json(json_path)
        analyzer = CoverageAnalyzer()
        analysis = analyzer.analyze(snapshot)
        reporter = CoverageReporter()

        if fmt == "json":
            return reporter.report_json(analysis)
        if fmt == "html":
            return reporter.report_html(analysis)
        return reporter.report_text(analysis)

    registry.register_async(
        "coverage-report",
        "Generate coverage report (text/json/html)",
        coverage_report_handler,
    )

    # ------------------------------------------------------------------
    # /coverage-optimize — Suggest tests to maximize coverage
    # ------------------------------------------------------------------
    async def coverage_optimize_handler(args: str) -> str:
        """
        Usage: /coverage-optimize <json-path> [--top N]
        """
        from lidco.coverage.analyzer import CoverageAnalyzer
        from lidco.coverage.collector import CoverageCollector
        from lidco.coverage.optimizer import CoverageOptimizer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /coverage-optimize <json-path> [--top N]"

        json_path = parts[0]
        top_n = 20

        i = 1
        while i < len(parts):
            if parts[i] == "--top" and i + 1 < len(parts):
                try:
                    top_n = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        collector = CoverageCollector()
        snapshot = collector.collect_from_json(json_path)
        analyzer = CoverageAnalyzer()
        analysis = analyzer.analyze(snapshot)
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)

        lines = [
            f"Coverage Optimization Plan ({plan.suggestion_count} suggestions):",
            f"  Current line rate: {plan.current_line_rate:.1%}",
            f"  Projected line rate: {plan.projected_line_rate:.1%}",
            f"  Total expected line gain: {plan.total_expected_gain}",
            "",
        ]

        for s in plan.suggestions[:top_n]:
            lines.append(
                f"  [P{s.priority}] {s.description} "
                f"(effort: {s.estimated_effort}, gain: +{s.expected_line_gain})"
            )

        return "\n".join(lines)

    registry.register_async(
        "coverage-optimize",
        "Suggest tests to maximize coverage",
        coverage_optimize_handler,
    )
