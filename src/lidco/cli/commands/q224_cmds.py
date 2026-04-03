"""Q224 CLI commands: /route, /model-stats, /quality-track, /cost-quality."""
from __future__ import annotations


def register(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q224 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /route <prompt>
    # ------------------------------------------------------------------

    async def route_handler(args: str) -> str:
        from lidco.routing.complexity_estimator import ComplexityEstimator
        from lidco.routing.model_selector import ModelSelector

        prompt = args.strip()
        if not prompt:
            return "Usage: /route <prompt>"
        estimator = ComplexityEstimator()
        result = estimator.estimate(prompt)
        selector = ModelSelector()
        selection = selector.select(result)
        return (
            f"Complexity: {result.level} (score={result.score})\n"
            f"Model: {selection.model}\n"
            f"Reason: {selection.reason}\n"
            f"Fallback: {', '.join(selection.fallback_chain) or 'none'}\n"
            f"Factors: {', '.join(result.factors) or 'none'}\n"
            f"Token estimate: {result.token_estimate}"
        )

    # ------------------------------------------------------------------
    # /model-stats [model]
    # ------------------------------------------------------------------

    async def model_stats_handler(args: str) -> str:
        from lidco.routing.quality_tracker import QualityTracker

        tracker = QualityTracker()
        model = args.strip() or None
        if model:
            avg = tracker.average(model)
            if avg is None:
                return f"No records for model '{model}'"
            return f"{model}: avg={avg:.4f}"
        summary = tracker.summary()
        if not summary:
            return "No quality records yet."
        lines = []
        for m, stats in summary.items():
            lines.append(f"{m}: avg={stats['avg']:.4f}, count={stats['count']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /quality-track <model> <score>
    # ------------------------------------------------------------------

    async def quality_track_handler(args: str) -> str:
        from lidco.routing.quality_tracker import QualityTracker

        parts = args.strip().split()
        if len(parts) < 2:
            return "Usage: /quality-track <model> <score> [task_type]"
        model = parts[0]
        try:
            score = float(parts[1])
        except ValueError:
            return "Score must be a number."
        task_type = parts[2] if len(parts) > 2 else "general"
        tracker = QualityTracker()
        rec = tracker.record(model, score, task_type)
        return f"Recorded: {rec.model} score={rec.score} type={rec.task_type}"

    # ------------------------------------------------------------------
    # /cost-quality [min_quality] [max_cost]
    # ------------------------------------------------------------------

    async def cost_quality_handler(args: str) -> str:
        from lidco.routing.cost_quality import CostQualityOptimizer

        optimizer = CostQualityOptimizer()
        summary = optimizer.summary()
        if summary["count"] == 0:
            return "No model profiles registered."
        parts = args.strip().split()
        min_q = float(parts[0]) if parts else 0.0
        max_c = float(parts[1]) if len(parts) > 1 else None
        rec = optimizer.recommend(min_quality=min_q, max_cost=max_c)
        if rec is None:
            return "No model meets the constraints."
        return (
            f"Recommended: {rec.model}\n"
            f"Quality: {rec.avg_quality:.4f}\n"
            f"Cost/token: {rec.avg_cost_per_token:.6f}\n"
            f"Latency: {rec.avg_latency_ms:.1f}ms"
        )

    registry.register(
        SlashCommand("route", "Estimate complexity and select model", route_handler)
    )
    registry.register(
        SlashCommand("model-stats", "Show quality stats per model", model_stats_handler)
    )
    registry.register(
        SlashCommand(
            "quality-track",
            "Record quality score for a model",
            quality_track_handler,
        )
    )
    registry.register(
        SlashCommand(
            "cost-quality",
            "Show cost-quality optimisation",
            cost_quality_handler,
        )
    )
