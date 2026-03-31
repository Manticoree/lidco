"""CLI commands for Q173 — Test Amplification & Mutation Testing."""

from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand


def register_q173_commands(registry) -> None:  # type: ignore[no-untyped-def]
    from lidco.testing.mutation_runner import MutationRunner, MutationConfig
    from lidco.testing.property_gen import PropertyTestGenerator
    from lidco.testing.coverage_gap import CoverageGapAnalyzer
    from lidco.testing.test_prioritizer import TestPrioritizer

    async def mutate_handler(args: str) -> str:
        args = args.strip()
        if not args:
            return (
                "Usage: /mutate <file_path>\n\n"
                "Run mutation testing on a file to verify test quality."
            )
        runner = MutationRunner()
        return (
            f"Mutation testing: {args}\n"
            f"Config: max_mutants={runner.config.max_mutants}, "
            f"types={runner.config.mutation_types}\n"
            "Run with actual file to see results."
        )

    async def proptest_handler(args: str) -> str:
        args = args.strip()
        if not args:
            return (
                "Usage: /proptest <function_name>\n\n"
                "Generate property-based tests for a function."
            )
        gen = PropertyTestGenerator()
        return (
            f"Property test generation for: {args}\n"
            f"Supported patterns: smoke, roundtrip, invariant\n"
            f"Strategies: {', '.join(gen.type_strategies.keys())}"
        )

    async def coverage_gaps_handler(args: str) -> str:
        parts = args.strip().split()
        top_n = 10
        for i, p in enumerate(parts):
            if p == "--top" and i + 1 < len(parts):
                try:
                    top_n = int(parts[i + 1])
                except ValueError:
                    pass
        analyzer = CoverageGapAnalyzer()
        return (
            f"Coverage gap analysis\n"
            f"Min risk threshold: {analyzer.min_risk}\n"
            f"Showing top {top_n} gaps\n"
            "Run coverage first: python -m pytest --cov --cov-report=json"
        )

    async def test_order_handler(args: str) -> str:
        args = args.strip()
        prioritizer = TestPrioritizer()
        if "--changed" in args:
            return (
                "Test ordering based on git changes\n"
                "Mappings registered: 0\n"
                "Run with actual git diff to prioritize tests."
            )
        return (
            "Usage: /test-order [--changed]\n\n"
            "Prioritize test execution order based on code changes."
        )

    registry.register(
        SlashCommand("mutate", "Run mutation testing on a file", mutate_handler)
    )
    registry.register(
        SlashCommand("proptest", "Generate property-based tests", proptest_handler)
    )
    registry.register(
        SlashCommand(
            "coverage-gaps", "Find untested code paths", coverage_gaps_handler
        )
    )
    registry.register(
        SlashCommand(
            "test-order", "Prioritize tests by change impact", test_order_handler
        )
    )
