"""
Q320 CLI commands — /pipeline-analyze, /pipeline-gen, /pipeline-optimize, /pipeline-monitor

Registered via register_q320_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q320_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q320 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /pipeline-analyze — Analyze CI pipeline config
    # ------------------------------------------------------------------
    async def pipeline_analyze_handler(args: str) -> str:
        """
        Usage: /pipeline-analyze [config-path] [repo-path]
        """
        from lidco.cicd.analyzer import PipelineAnalyzer

        parts = shlex.split(args) if args.strip() else []
        config_path: str | None = None
        repo = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--config" and i + 1 < len(parts):
                config_path = parts[i + 1]
                i += 2
            else:
                repo = parts[i]
                i += 1

        analyzer = PipelineAnalyzer(repo)
        result = analyzer.analyze(config_path=config_path)

        lines = [
            f"Pipeline Analysis ({result.provider}): {result.total_stages} stages",
            f"Estimated total duration: {result.estimated_total_duration:.0f}s",
            "",
        ]

        if result.bottlenecks:
            lines.append("Bottlenecks:")
            for b in result.bottlenecks:
                lines.append(f"  [{b.kind}] {b.description}")
                lines.append(f"    -> {b.suggestion}")
            lines.append("")

        if result.cache_opportunities:
            lines.append("Cache opportunities:")
            for c in result.cache_opportunities:
                lines.append(f"  - {c}")
            lines.append("")

        if result.parallelization_suggestions:
            lines.append("Parallelization:")
            for p in result.parallelization_suggestions:
                lines.append(f"  - {p}")

        if result.total_stages == 0:
            lines.append("No CI pipeline config detected.")

        return "\n".join(lines)

    registry.register_async(
        "pipeline-analyze",
        "Analyze CI pipeline config for bottlenecks",
        pipeline_analyze_handler,
    )

    # ------------------------------------------------------------------
    # /pipeline-gen — Generate CI config from project
    # ------------------------------------------------------------------
    async def pipeline_gen_handler(args: str) -> str:
        """
        Usage: /pipeline-gen [--provider github|gitlab|circleci] [--language LANG] [repo-path]
        """
        from lidco.cicd.generator import PipelineGenerator

        parts = shlex.split(args) if args.strip() else []
        provider = "github"
        language: str | None = None
        repo = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--provider" and i + 1 < len(parts):
                provider = parts[i + 1]
                i += 2
            elif parts[i] == "--language" and i + 1 < len(parts):
                language = parts[i + 1]
                i += 2
            else:
                repo = parts[i]
                i += 1

        gen = PipelineGenerator(repo)
        try:
            result = gen.generate(provider=provider, language=language)
        except ValueError as exc:
            return f"Error: {exc}"

        lines = [
            f"Generated {result.provider} pipeline for {result.language}:",
            f"Stages: {len(result.stages)}",
            "",
            result.raw_config,
        ]
        return "\n".join(lines)

    registry.register_async(
        "pipeline-gen",
        "Generate CI config from project structure",
        pipeline_gen_handler,
    )

    # ------------------------------------------------------------------
    # /pipeline-optimize — Optimize pipeline config
    # ------------------------------------------------------------------
    async def pipeline_optimize_handler(args: str) -> str:
        """
        Usage: /pipeline-optimize [config-path] [repo-path]
        """
        from lidco.cicd.analyzer import PipelineAnalyzer
        from lidco.cicd.optimizer import PipelineOptimizer

        parts = shlex.split(args) if args.strip() else []
        config_path: str | None = None
        repo = "."

        i = 0
        while i < len(parts):
            if parts[i] == "--config" and i + 1 < len(parts):
                config_path = parts[i + 1]
                i += 2
            else:
                repo = parts[i]
                i += 1

        analyzer = PipelineAnalyzer(repo)
        analysis = analyzer.analyze(config_path=config_path)

        if analysis.total_stages == 0:
            return "No CI pipeline config detected. Nothing to optimize."

        stage_dicts = [
            {
                "name": s.name,
                "steps": s.steps,
                "has_cache": s.has_cache,
                "depends_on": s.depends_on,
                "estimated_duration": s.estimated_duration,
            }
            for s in analysis.stages
        ]

        optimizer = PipelineOptimizer(repo)
        result = optimizer.optimize(stage_dicts)

        lines = [
            f"Pipeline Optimization ({analysis.provider}):",
            f"Original duration: {result.original_duration:.0f}s",
            f"Optimized duration: {result.optimized_duration:.0f}s",
            f"Estimated savings: {result.total_estimated_savings:.0f}s",
            "",
        ]

        if result.optimizations:
            lines.append("Optimizations:")
            for o in result.optimizations:
                lines.append(f"  [{o.kind}] {o.description} (-{o.estimated_savings:.0f}s)")
            lines.append("")

        if result.skip_unchanged_paths:
            lines.append("Skip-unchanged paths:")
            for p in result.skip_unchanged_paths:
                lines.append(f"  - {p}")

        return "\n".join(lines)

    registry.register_async(
        "pipeline-optimize",
        "Optimize CI pipeline for faster builds",
        pipeline_optimize_handler,
    )

    # ------------------------------------------------------------------
    # /pipeline-monitor — Pipeline monitoring dashboard
    # ------------------------------------------------------------------
    async def pipeline_monitor_handler(args: str) -> str:
        """
        Usage: /pipeline-monitor [--pipeline NAME] [--limit N]
        """
        from lidco.cicd.monitor import PipelineMonitor

        parts = shlex.split(args) if args.strip() else []
        pipeline_name: str | None = None
        limit = 10

        i = 0
        while i < len(parts):
            if parts[i] == "--pipeline" and i + 1 < len(parts):
                pipeline_name = parts[i + 1]
                i += 2
            elif parts[i] == "--limit" and i + 1 < len(parts):
                try:
                    limit = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1

        monitor = PipelineMonitor()
        runs = monitor.get_runs(pipeline=pipeline_name, limit=limit)

        if not runs:
            return "No pipeline runs recorded yet."

        lines = ["Pipeline Monitor:"]

        if pipeline_name:
            stats = monitor.get_stats(pipeline_name)
            lines.extend([
                f"Pipeline: {stats.pipeline}",
                f"Total runs: {stats.total_runs}",
                f"Success rate: {stats.success_rate:.0%}",
                f"Avg duration: {stats.avg_duration:.1f}s",
                "",
            ])
            if stats.flaky_tests:
                lines.append("Flaky tests:")
                for ft in stats.flaky_tests:
                    lines.append(f"  {ft.name}: {ft.flake_rate:.0%} flake rate ({ft.failure_count}/{ft.total_runs})")
                lines.append("")

        lines.append("Recent runs:")
        for r in runs[-limit:]:
            dur_str = f" ({r.duration:.1f}s)" if r.duration > 0 else ""
            lines.append(f"  [{r.status}] {r.pipeline} #{r.run_id}{dur_str}")

        return "\n".join(lines)

    registry.register_async(
        "pipeline-monitor",
        "Real-time pipeline status and analytics",
        pipeline_monitor_handler,
    )
