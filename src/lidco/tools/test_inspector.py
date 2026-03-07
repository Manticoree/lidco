"""Live variable capture — runs pytest --showlocals to get variable state at failure."""
from __future__ import annotations

import asyncio
import re
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

# Match lines like:
#   test_file.py:45: in test_name
_FRAME_RE = re.compile(r"^\s*(.+\.py:\d+: in .+)$")

# Match variable assignment lines like:
#   varname       = value
_VAR_RE = re.compile(r"^\s{4,}(\w+)\s+= (.+)$")


class TestInspectorTool(BaseTool):
    """Run a failing test with --showlocals to capture variable values at failure."""

    @property
    def name(self) -> str:
        return "capture_failure_locals"

    @property
    def description(self) -> str:
        return (
            "Run a failing test with --showlocals to capture variable values at failure."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="test_path",
                type="string",
                description="Path to test file or test ID.",
                required=True,
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Maximum seconds to wait for pytest.",
                required=False,
                default=60,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    # ------------------------------------------------------------------

    def _parse_frames(self, output: str) -> dict[str, dict[str, str]]:
        """Parse pytest --showlocals output into a dict of frame → vars."""
        frames: dict[str, dict[str, str]] = {}
        current_frame: str | None = None

        for line in output.splitlines():
            frame_m = _FRAME_RE.match(line)
            if frame_m:
                current_frame = frame_m.group(1).strip()
                frames[current_frame] = {}
                continue

            if current_frame is not None:
                var_m = _VAR_RE.match(line)
                if var_m:
                    var_name = var_m.group(1)
                    var_value = var_m.group(2)
                    frames[current_frame][var_name] = var_value

        return frames

    def _format_frames(self, frames: dict[str, dict[str, str]]) -> str:
        """Format captured frames as a readable string."""
        if not frames:
            return "## Variable State at Failure\n\n(no local variables captured)"

        lines: list[str] = ["## Variable State at Failure", ""]
        for frame, variables in frames.items():
            lines.append(f"**{frame}:**")
            if variables:
                for var_name, var_value in variables.items():
                    none_marker = "  ⚠ (None value)" if var_value.strip() == "None" else ""
                    lines.append(f"- {var_name} = {var_value}{none_marker}")
            else:
                lines.append("  (no variables captured)")
            lines.append("")

        return "\n".join(lines).rstrip()

    # ------------------------------------------------------------------

    async def _run(self, **kwargs: Any) -> ToolResult:
        test_path: str = kwargs["test_path"]
        timeout: int = int(kwargs.get("timeout", 60))

        cmd = [
            "python",
            "-m",
            "pytest",
            test_path,
            "--tb=long",
            "--showlocals",
            "-x",
            "-q",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")
            combined = output + err_output
        except asyncio.TimeoutError:
            return ToolResult(
                output=f"pytest timed out after {timeout}s",
                success=False,
                error=f"Timeout after {timeout}s",
                metadata={"frames": {}},
            )
        except FileNotFoundError:
            return ToolResult(
                output="pytest not found — install it first.",
                success=False,
                error="pytest not found",
                metadata={"frames": {}},
            )

        frames = self._parse_frames(combined)
        formatted = self._format_frames(frames)

        return ToolResult(
            output=formatted,
            success=False,  # test was failing — always False
            metadata={"frames": frames},
        )
