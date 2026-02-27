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

            rc = process.returncode or 0
            error_msg: str | None = None
            if rc != 0:
                last_stderr = ""
                if stderr_text.strip():
                    nonempty = [ln for ln in stderr_text.splitlines() if ln.strip()]
                    if nonempty:
                        last_stderr = nonempty[-1][:200]
                error_msg = (
                    f"Exit code {rc}: {last_stderr}"
                    if last_stderr
                    else f"Exit code {rc}"
                )
            return ToolResult(
                output=output,
                success=rc == 0,
                error=error_msg,
                metadata={"exit_code": rc, "command": command},
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            return ToolResult(
                output="", success=False, error=f"Command timed out after {timeout}s"
            )
