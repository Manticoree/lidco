"""Execution trace recorder tool — LDB-style hybrid trace for failing tests."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class TraceInspectorTool(BaseTool):
    """Record an execution trace for a failing test and optionally save/compare baselines.

    Runs the failing test with ``--tb=long --showlocals``, parses frame +
    local-variable data, and optionally detects anomalies against a saved
    passing-run baseline.
    """

    @property
    def name(self) -> str:
        return "capture_execution_trace"

    @property
    def description(self) -> str:
        return (
            "Record an execution trace for a failing test: captures frame stack and "
            "local variables at each frame in the target file. Can save a baseline "
            "from a passing run and detect anomalies (unexpected None, type drift, "
            "value changes) when run against a failing test."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="test_command",
                type="string",
                description=(
                    "Pytest node ID or path of the failing test "
                    "(e.g., 'tests/unit/test_foo.py::test_bar')."
                ),
                required=True,
            ),
            ToolParameter(
                name="target_file",
                type="string",
                description=(
                    "Source file to focus the trace on "
                    "(e.g., 'src/lidco/core/session.py')."
                ),
                required=True,
            ),
            ToolParameter(
                name="save_baseline",
                type="boolean",
                description=(
                    "When True, treat this run as a passing run and save the trace "
                    "as a baseline for future anomaly detection."
                ),
                required=False,
                default=False,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Maximum seconds to wait for pytest (default 30).",
                required=False,
                default=30,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    # ── Execution ─────────────────────────────────────────────────────────

    async def _run(self, **kwargs: Any) -> ToolResult:
        test_command: str = kwargs["test_command"]
        target_file: str = kwargs["target_file"]
        save_as_baseline: bool = bool(kwargs.get("save_baseline", False))
        timeout: int = int(kwargs.get("timeout", 30))

        project_dir = Path.cwd()

        from lidco.core.trace_recorder import (
            detect_anomalies,
            format_trace_session,
            load_baseline,
            record_trace,
            save_baseline,
        )

        session = await record_trace(
            test_command=test_command,
            target_file=target_file,
            project_dir=project_dir,
            timeout_s=float(timeout),
        )

        if session is None:
            return ToolResult(
                success=False,
                output="",
                error="Trace recording failed (timeout or subprocess error).",
            )

        if save_as_baseline:
            save_baseline(session, project_dir)
            saved_msg = f"\n\n*Baseline saved to `.lidco/trace_baseline.json`*"
        else:
            saved_msg = ""

        trace_str = format_trace_session(session)

        # Anomaly detection when baseline is available
        anomaly_str = ""
        if not save_as_baseline:
            baseline = load_baseline(project_dir)
            anomalies = detect_anomalies(session, baseline)
            if anomalies:
                lines = ["## Trace Anomalies\n"]
                for a in anomalies[:10]:
                    lines.append(
                        f"- **Line {a.line}** `{a.variable}` "
                        f"({a.anomaly_type}): "
                        f"failing=`{a.failing_value}` "
                        f"vs baseline=`{a.baseline_value}`"
                    )
                anomaly_str = "\n" + "\n".join(lines)

        output = (trace_str or "*No trace events captured.*") + anomaly_str + saved_msg

        return ToolResult(success=True, output=output, error=None)
