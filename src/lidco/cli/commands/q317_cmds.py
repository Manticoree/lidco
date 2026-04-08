"""
Q317 CLI commands — /e2e-plan, /e2e-gen, /e2e-failure, /e2e-optimize

Registered via register_q317_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q317_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q317 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /e2e-plan — Plan E2E test suites
    # ------------------------------------------------------------------
    async def e2e_plan_handler(args: str) -> str:
        """
        Usage: /e2e-plan [--step-duration N] [journey_name ...]
        """
        from lidco.e2e_intel.planner import (
            E2ETestPlanner,
            Priority,
            UserJourney,
            UserStep,
        )

        parts = shlex.split(args) if args.strip() else []
        step_duration = 5.0
        journey_names: list[str] = []

        i = 0
        while i < len(parts):
            if parts[i] == "--step-duration" and i + 1 < len(parts):
                try:
                    step_duration = float(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                journey_names.append(parts[i])
                i += 1

        if not journey_names:
            journey_names = ["login", "checkout", "search"]

        planner = E2ETestPlanner(default_step_duration_s=step_duration)
        journeys = [
            UserJourney(
                name=name,
                steps=(
                    UserStep(action="navigate", target="page"),
                    UserStep(action="click", target="button"),
                ),
                priority=Priority.HIGH if idx == 0 else Priority.MEDIUM,
            )
            for idx, name in enumerate(journey_names)
        ]
        planner = planner.add_journeys(journeys)
        plan = planner.plan()

        lines = [
            f"E2E Test Plan: {len(plan.entries)} test(s)",
            f"Estimated duration: {plan.total_estimated_duration_s}s",
            f"Critical paths: {len(plan.critical_paths)}",
            "",
        ]
        for entry in plan.entries:
            lines.append(
                f"  [{entry.priority.value}] {entry.journey_name} "
                f"({entry.estimated_duration_s}s)"
            )
        for cp in plan.critical_paths:
            lines.append(f"  Critical: {cp.name} (risk={cp.risk_score})")

        return "\n".join(lines)

    registry.register_async(
        "e2e-plan",
        "Plan E2E test suites with journey mapping",
        e2e_plan_handler,
    )

    # ------------------------------------------------------------------
    # /e2e-gen — Generate E2E test code
    # ------------------------------------------------------------------
    async def e2e_gen_handler(args: str) -> str:
        """
        Usage: /e2e-gen [--framework playwright|cypress] [--url URL] <test_name>
        """
        from lidco.e2e_intel.generator import (
            Assertion,
            AssertionType,
            E2ETestGenerator,
            Framework,
            TestStep,
        )

        parts = shlex.split(args) if args.strip() else []
        framework = Framework.PLAYWRIGHT
        base_url = "http://localhost:3000"
        test_name = "sample_test"

        i = 0
        while i < len(parts):
            if parts[i] == "--framework" and i + 1 < len(parts):
                val = parts[i + 1].lower()
                if val == "cypress":
                    framework = Framework.CYPRESS
                i += 2
            elif parts[i] == "--url" and i + 1 < len(parts):
                base_url = parts[i + 1]
                i += 2
            else:
                test_name = parts[i]
                i += 1

        gen = E2ETestGenerator(framework=framework, base_url=base_url)
        test = gen.generate_test(
            name=test_name,
            steps=[
                TestStep(action="navigate", value=base_url),
                TestStep(action="click", selector="#submit"),
            ],
            assertions=[
                Assertion(
                    assertion_type=AssertionType.VISIBLE, selector="#result"
                ),
            ],
        )

        lines = [
            f"Generated E2E test: {test.name} ({test.framework.value})",
            f"Steps: {len(test.steps)}, Assertions: {len(test.assertions)}",
            "",
            test.code,
        ]
        return "\n".join(lines)

    registry.register_async(
        "e2e-gen",
        "Generate E2E test code (Playwright/Cypress)",
        e2e_gen_handler,
    )

    # ------------------------------------------------------------------
    # /e2e-failure — Analyze E2E test failures
    # ------------------------------------------------------------------
    async def e2e_failure_handler(args: str) -> str:
        """
        Usage: /e2e-failure <test_name> <error_message>
        """
        from lidco.e2e_intel.failure import E2EFailureAnalyzer, FailureContext

        parts = shlex.split(args) if args.strip() else []
        test_name = parts[0] if len(parts) >= 1 else "unknown_test"
        error_msg = " ".join(parts[1:]) if len(parts) >= 2 else "Test failed"

        analyzer = E2EFailureAnalyzer()
        ctx = FailureContext(test_name=test_name, error_message=error_msg)
        report = analyzer.analyze(ctx)

        lines = [
            f"Failure Analysis: {report.test_name}",
            f"Primary cause: {report.primary_category.value}",
            f"Flaky: {report.is_flaky}",
            "",
        ]
        for rc in report.root_causes:
            lines.append(
                f"  [{rc.confidence:.0%}] {rc.category.value}: {rc.summary}"
            )
            if rc.suggested_fix:
                lines.append(f"    Fix: {rc.suggested_fix}")

        return "\n".join(lines)

    registry.register_async(
        "e2e-failure",
        "Analyze E2E test failures for root cause",
        e2e_failure_handler,
    )

    # ------------------------------------------------------------------
    # /e2e-optimize — Optimize E2E test suite
    # ------------------------------------------------------------------
    async def e2e_optimize_handler(args: str) -> str:
        """
        Usage: /e2e-optimize [--parallel N] [--changed file1,file2,...]
        """
        from lidco.e2e_intel.optimizer import E2ETestOptimizer, TestMetadata

        parts = shlex.split(args) if args.strip() else []
        max_parallel = 4
        changed_files: list[str] = []

        i = 0
        while i < len(parts):
            if parts[i] == "--parallel" and i + 1 < len(parts):
                try:
                    max_parallel = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--changed" and i + 1 < len(parts):
                changed_files = parts[i + 1].split(",")
                i += 2
            else:
                i += 1

        # Demo tests for CLI output
        tests = [
            TestMetadata(name="login_flow", duration_ms=5000, tags=("auth",)),
            TestMetadata(name="checkout_flow", duration_ms=8000, tags=("payment",)),
            TestMetadata(
                name="search_flow",
                duration_ms=3000,
                tags=("search",),
                changed_files=("search.py",),
            ),
        ]

        optimizer = E2ETestOptimizer(max_parallel=max_parallel)
        report = optimizer.optimize(tests, changed_files=changed_files)

        lines = [
            f"E2E Optimization Report",
            f"Speedup: {report.estimated_speedup}x",
            f"Original: {report.original_duration_ms}ms -> Optimized: {report.optimized_duration_ms}ms",
            f"Parallel groups: {len(report.parallel_groups)}",
            f"Shared setups: {len(report.shared_setups)}",
            f"Selected: {len(report.selection.selected)}, Skipped: {len(report.selection.skipped)}",
            "",
        ]
        for g in report.parallel_groups:
            lines.append(
                f"  Group {g.group_id}: {', '.join(g.tests)} ({g.estimated_duration_ms}ms)"
            )

        return "\n".join(lines)

    registry.register_async(
        "e2e-optimize",
        "Optimize E2E test suite execution",
        e2e_optimize_handler,
    )
