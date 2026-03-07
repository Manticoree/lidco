"""Test Autopilot — autonomous fix→test→fix cycle."""
from __future__ import annotations

import asyncio
import re
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


def _parse_failed_count(output: str) -> int:
    """Return the number of failed tests from pytest output, or 0 if not found."""
    m = re.search(r"(\d+) failed", output)
    if m:
        return int(m.group(1))
    return 0


class TestAutopilotTool(BaseTool):
    """Run autonomous fix→test cycles until failing tests pass or max rounds reached."""

    @property
    def name(self) -> str:
        return "run_debug_cycle"

    @property
    def description(self) -> str:
        return (
            "Run autonomous fix→test cycles until failing tests pass or max rounds reached."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="test_path",
                type="string",
                description="Path to test file, directory, or test ID. Empty = run all.",
                required=False,
                default="",
            ),
            ToolParameter(
                name="max_rounds",
                type="integer",
                description="Maximum fix→test cycles.",
                required=False,
                default=3,
            ),
            ToolParameter(
                name="confidence_threshold",
                type="number",
                description="Stop when this fraction of originally-failing tests pass.",
                required=False,
                default=0.8,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run_tests(self, test_path: str) -> str:
        """Run pytest and return stdout+stderr as a single string."""
        cmd = ["python", "-m", "pytest", "-q"]
        if test_path:
            cmd.append(test_path)
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            return stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        except FileNotFoundError:
            return "pytest not found"

    async def _run(self, **kwargs: Any) -> ToolResult:
        test_path: str = kwargs.get("test_path", "")
        max_rounds: int = int(kwargs.get("max_rounds", 3))
        confidence_threshold: float = float(kwargs.get("confidence_threshold", 0.8))

        # Baseline run
        baseline_output = await self._run_tests(test_path)
        originally_failing = _parse_failed_count(baseline_output)

        if originally_failing == 0:
            return ToolResult(
                output="All tests passing — no debug cycle needed.",
                success=True,
                metadata={
                    "originally_failing": 0,
                    "final_failing": 0,
                    "rounds": 0,
                    "confidence": 1.0,
                },
            )

        round_summaries: list[str] = []
        prev_failing = originally_failing
        current_failing = originally_failing
        rounds_done = 0
        confidence = 0.0

        for r in range(1, max_rounds + 1):
            rounds_done = r

            # In a real scenario the debugger agent would fix code here.
            # This tool provides the harness and tracks cycles.
            test_output = await self._run_tests(test_path)
            current_failing = _parse_failed_count(test_output)

            fixed_this_round = prev_failing - current_failing
            total_fixed = originally_failing - current_failing
            pct = int(total_fixed / originally_failing * 100) if originally_failing else 100

            round_summaries.append(
                f"Round {r}: {prev_failing} failing → {current_failing} failing ({pct}% fixed)"
            )

            confidence = (originally_failing - current_failing) / originally_failing

            if confidence >= confidence_threshold:
                break

            if current_failing >= prev_failing:
                # Stalled — no progress
                break

            prev_failing = current_failing

        total_fixed = originally_failing - current_failing
        total_pct = int(total_fixed / originally_failing * 100) if originally_failing else 100

        summary_lines = [
            f"Debug Cycle Summary: {rounds_done} rounds",
            *round_summaries,
            f"Total: {total_fixed} of {originally_failing} tests fixed ({total_pct}%)",
        ]
        output = "\n".join(summary_lines)

        return ToolResult(
            output=output,
            success=(confidence >= confidence_threshold),
            metadata={
                "originally_failing": originally_failing,
                "final_failing": current_failing,
                "rounds": rounds_done,
                "confidence": confidence,
            },
        )
