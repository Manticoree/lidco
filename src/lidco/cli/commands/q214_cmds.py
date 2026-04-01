"""Q214 CLI commands: /gen-test, /property-test, /mutate, /coverage-gaps."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q214 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /gen-test
    # ------------------------------------------------------------------

    async def gen_test_handler(args: str) -> str:
        import os
        from lidco.test_intel.case_generator import TestCaseGenerator

        parts = args.strip().split(None, 1)
        if not parts:
            return "Usage: /gen-test <file> [function_name]"
        filepath = parts[0]
        func_name = parts[1] if len(parts) > 1 else ""

        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()

        gen = TestCaseGenerator()
        cases = gen.generate(source, func_name)
        if not cases:
            return "No test cases generated."
        code = gen.to_code(cases)
        return f"Generated {len(cases)} test cases:\n\n{code}"

    # ------------------------------------------------------------------
    # /property-test
    # ------------------------------------------------------------------

    async def property_test_handler(args: str) -> str:
        from lidco.test_intel.property_builder import PropertyBuilder

        parts = args.strip().split()
        if not parts:
            return "Usage: /property-test <function_name> [param:type ...]"

        func_name = parts[0]
        params: list[tuple[str, str]] = []
        for p in parts[1:]:
            if ":" in p:
                name, hint = p.split(":", 1)
                params.append((name, hint))
            else:
                params.append((p, ""))

        builder = PropertyBuilder()
        spec = builder.build(func_name, params)
        code = builder.to_code(spec)
        return f"Property spec for {func_name}:\n\n{code}"

    # ------------------------------------------------------------------
    # /mutate
    # ------------------------------------------------------------------

    async def mutate_handler(args: str) -> str:
        import os
        from lidco.test_intel.mutation_runner import MutationRunner

        filepath = args.strip()
        if not filepath:
            return "Usage: /mutate <file>"

        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()

        runner = MutationRunner()
        mutants = runner.generate_mutants(source, filepath)
        if not mutants:
            return "No mutants generated."
        report = runner.survival_report(mutants)
        return report

    # ------------------------------------------------------------------
    # /coverage-gaps
    # ------------------------------------------------------------------

    async def coverage_gaps_handler(args: str) -> str:
        import json
        import os
        from lidco.test_intel.coverage_gap import CoverageGapFinder

        filepath = args.strip()
        if not filepath:
            return "Usage: /coverage-gaps <coverage_json_file>"

        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        finder = CoverageGapFinder()
        gaps = finder.parse_coverage(data)
        if not gaps:
            return "No coverage gaps found."
        prioritized = finder.prioritize(gaps)
        return finder.summary(prioritized)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    registry.register(SlashCommand("gen-test", "Generate test cases from source", gen_test_handler))
    registry.register(SlashCommand("property-test", "Build property-based test spec", property_test_handler))
    registry.register(SlashCommand("mutate", "Run mutation analysis on source", mutate_handler))
    registry.register(SlashCommand("coverage-gaps", "Find coverage gaps from JSON", coverage_gaps_handler))
