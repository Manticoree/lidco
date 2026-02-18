"""Bash/shell command execution tool."""

from __future__ import annotations

import asyncio
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class BashTool(BaseTool):
    """Execute shell commands."""

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "Execute shell command and return output."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The shell command to execute.",
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout in seconds.",
                required=False,
                default=120,
            ),
            ToolParameter(
                name="cwd",
                type="string",
                description="Working directory for the command.",
                required=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        command: str = kwargs["command"]
        timeout: int = kwargs.get("timeout", 120)
        cwd: str | None = kwargs.get("cwd")

        # Block dangerous commands
        dangerous = ["rm -rf /", "rm -rf /*", ":(){ :|:& };:", "mkfs", "> /dev/sda"]
        for d in dangerous:
            if d in command:
                return ToolResult(
                    output="", success=False, error=f"Blocked dangerous command: {command}"
                )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

            output = stdout_text
            if stderr_text:
                output += f"\n[stderr]\n{stderr_text}"

            # Truncate very long outputs
            if len(output) > 15000:
                output = output[:8000] + "\n\n... (truncated) ...\n\n" + output[-7000:]

            return ToolResult(
                output=output,
                success=process.returncode == 0,
                error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
                metadata={"exit_code": process.returncode or 0, "command": command},
            )
        except asyncio.TimeoutError:
            return ToolResult(
                output="", success=False, error=f"Command timed out after {timeout}s"
            )
