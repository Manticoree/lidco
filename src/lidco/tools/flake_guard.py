"""FlakeGuard tool — detect flaky tests by running the suite multiple times.

Wraps :func:`~lidco.core.flake_runner.run_tests_multi` and
:func:`~lidco.core.flake_classifier.classify_many` to produce a single
Markdown report.

Tool name: ``flake_guard``
"""

from __future__ import annotations

from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class FlakeGuardTool(BaseTool):
    """Run the test suite N times and detect flaky (non-deterministic) tests.

    Executes pytest via subprocess, collects pass/fail outcomes across all
    runs, computes flake rates, classifies root causes (timing / ordering /
    resource / random), and returns a Markdown report.
    """

    @property
    def name(self) -> str:
        return "flake_guard"

    @property
    def description(self) -> str:
        return (
            "Detect flaky (non-deterministic) tests by running the suite multiple times. "
            "Reports flake rates, root-cause categories (timing/ordering/resource/random), "
            "and suggested fixes."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="test_paths",
                type="string",
                description=(
                    "Space-separated test paths to pass to pytest "
                    "(e.g. 'tests/' or 'tests/unit/test_foo.py'). "
                    "Defaults to 'tests/'."
                ),
                required=False,
                default="tests/",
            ),
            ToolParameter(
                name="runs",
                type="integer",
                description="Number of times to run the test suite (default 3, max 10).",
                required=False,
                default=3,
            ),
            ToolParameter(
                name="min_flake_rate",
                type="number",
                description=(
                    "Minimum flake rate (0–1) to flag a test as flaky. "
                    "Default 0.1 (10%)."
                ),
                required=False,
                default=0.1,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        from lidco.core.flake_classifier import classify_many
        from lidco.core.flake_report import format_flake_report
        from lidco.core.flake_runner import MultiRunConfig, run_tests_multi

        test_paths_raw: str = str(kwargs.get("test_paths", "tests/"))
        runs: int = int(kwargs.get("runs", 3))
        min_flake_rate: float = float(kwargs.get("min_flake_rate", 0.1))

        # Validate
        if runs < 1:
            return ToolResult(
                output="Parameter 'runs' must be at least 1.",
                success=False,
                error="Invalid parameter: runs < 1",
                metadata={},
            )
        if runs > 10:
            runs = 10  # cap silently to avoid accidental long runs

        test_paths = [p.strip() for p in test_paths_raw.split() if p.strip()]
        if not test_paths:
            test_paths = ["tests/"]

        cfg = MultiRunConfig(
            test_paths=test_paths,
            runs=runs,
            min_flake_rate=min_flake_rate,
            min_runs_for_flake=max(1, runs // 2),
        )

        multi_result = await run_tests_multi(cfg)

        # Classify flaky tests — gather outcomes from history
        # Build a simple outcomes map from history records (error_msg not stored
        # per-run in FlakeHistory, so pass empty outcomes for classification).
        classifications = classify_many(multi_result.flaky_tests, {})

        report = format_flake_report(
            history=multi_result.history,
            flaky_records=multi_result.flaky_tests,
            classifications=classifications,
            run_errors=multi_result.run_errors,
        )

        has_flakes = len(multi_result.flaky_tests) > 0
        return ToolResult(
            output=report,
            success=not has_flakes,
            metadata={
                "total_runs": multi_result.total_runs,
                "flaky_count": len(multi_result.flaky_tests),
                "total_tests": multi_result.history.total_tests,
                "run_errors": len(multi_result.run_errors),
            },
        )
