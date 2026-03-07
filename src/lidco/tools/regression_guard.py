"""Regression guard — detects tests that regressed after a fix."""
from __future__ import annotations

import asyncio
import re
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


def _parse_test_results(output: str) -> dict[str, str]:
    """Parse pytest verbose output to extract per-test pass/fail status.

    Handles lines like:
      PASSED tests/test_foo.py::test_bar
      FAILED tests/test_foo.py::test_bar
      FAILED tests/test_foo.py::test_bar - AssertionError: ...

    Returns a mapping of test_id -> "pass" or "fail".
    """
    results: dict[str, str] = {}
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("PASSED "):
            test_id = stripped[7:].split(" - ")[0].split(" ")[0].strip()
            if test_id:
                results[test_id] = "pass"
        elif stripped.startswith("FAILED "):
            test_id = stripped[7:].split(" - ")[0].split(" ")[0].strip()
            if test_id:
                results[test_id] = "fail"
    return results


class RegressionGuardTool(BaseTool):
    """Compare test results before and after a fix to detect regressions."""

    @property
    def name(self) -> str:
        return "check_regressions"

    @property
    def description(self) -> str:
        return "Compare test results before and after a fix to detect regressions."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="before_snapshot",
                type="object",
                description="Dict mapping test_id to 'pass' or 'fail' from before the fix",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Maximum seconds to wait for the test suite.",
                required=False,
                default=120,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        before_snapshot: dict[str, str] = kwargs.get("before_snapshot", {})
        timeout: int = int(kwargs.get("timeout", 120))

        cmd = ["python", "-m", "pytest", "-v", "--tb=no", "-q"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            stdout_text = stdout.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            return ToolResult(
                output="", success=False, error=f"Tests timed out after {timeout}s"
            )
        except FileNotFoundError:
            return ToolResult(
                output="", success=False, error="pytest not found — install it first."
            )

        after_results = _parse_test_results(stdout_text)

        fixed: list[str] = []
        regressed: list[str] = []

        # Tests that were failing before and pass now
        for test_id, before_status in before_snapshot.items():
            after_status = after_results.get(test_id)
            if before_status == "fail" and after_status == "pass":
                fixed.append(test_id)
            elif before_status == "pass" and after_status == "fail":
                regressed.append(test_id)

        # Tests with no before_snapshot that are now failing are treated as regressions
        # only if before_snapshot is empty (all currently failing = regressed)
        if not before_snapshot:
            regressed = [tid for tid, status in after_results.items() if status == "fail"]
            fixed = []

        net_gain = len(fixed) - len(regressed)
        success = len(regressed) == 0

        lines: list[str] = [
            "Regression Analysis:",
            f"✓ Fixed: {len(fixed)} tests",
            f"✗ Regressed: {len(regressed)} tests",
            f"Net gain: {net_gain:+d} tests",
        ]

        if regressed:
            lines.append("")
            lines.append("⚠ REGRESSIONS DETECTED:")
            for test_id in regressed:
                lines.append(f"  - {test_id} (was PASS → now FAIL)")
        else:
            lines.append("")
            lines.append("✓ No regressions detected")

        return ToolResult(
            output="\n".join(lines),
            success=success,
            error=None if success else f"{len(regressed)} regression(s) detected",
            metadata={
                "fixed": fixed,
                "regressed": regressed,
                "net_gain": net_gain,
            },
        )
