"""CLI commands for Q186 — Multi-Agent PR Review Pipeline."""

from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q186_commands(registry) -> None:
    """Register /review-pipeline, /review-comments, /review-failures, /review-types."""

    from lidco.review.pipeline import ReviewPipeline
    from lidco.review.agents.comment_analyzer import CommentAnalyzer, PRTestAnalyzer
    from lidco.review.agents.failure_hunter import SilentFailureHunter, TypeDesignAnalyzer
    from lidco.review.agents.quality import CodeQualityReviewer, CodeSimplifier

    async def review_pipeline_handler(args: str) -> str:
        diff_text = args.strip()
        if not diff_text:
            return "Usage: /review-pipeline <diff_text>"
        pipeline = ReviewPipeline(diff_text, [])
        pipeline = pipeline.add_agent(CommentAnalyzer())
        pipeline = pipeline.add_agent(PRTestAnalyzer())
        pipeline = pipeline.add_agent(SilentFailureHunter())
        pipeline = pipeline.add_agent(TypeDesignAnalyzer())
        pipeline = pipeline.add_agent(CodeQualityReviewer())
        pipeline = pipeline.add_agent(CodeSimplifier())
        report = pipeline.run()
        return report.format()

    async def review_comments_handler(args: str) -> str:
        diff_text = args.strip()
        if not diff_text:
            return "Usage: /review-comments <diff_text>"
        pipeline = ReviewPipeline(diff_text, [])
        pipeline = pipeline.add_agent(CommentAnalyzer())
        report = pipeline.run()
        return report.format()

    async def review_failures_handler(args: str) -> str:
        diff_text = args.strip()
        if not diff_text:
            return "Usage: /review-failures <diff_text>"
        pipeline = ReviewPipeline(diff_text, [])
        pipeline = pipeline.add_agent(SilentFailureHunter())
        report = pipeline.run()
        return report.format()

    async def review_types_handler(args: str) -> str:
        diff_text = args.strip()
        if not diff_text:
            return "Usage: /review-types <diff_text>"
        pipeline = ReviewPipeline(diff_text, [])
        pipeline = pipeline.add_agent(TypeDesignAnalyzer())
        report = pipeline.run()
        return report.format()

    registry.register(SlashCommand("review-pipeline", "Run full multi-agent review pipeline", review_pipeline_handler))
    registry.register(SlashCommand("review-comments", "Analyze comments and docstrings", review_comments_handler))
    registry.register(SlashCommand("review-failures", "Hunt for silent failures", review_failures_handler))
    registry.register(SlashCommand("review-types", "Analyze type design quality", review_types_handler))
