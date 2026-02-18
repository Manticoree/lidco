"""Git operations tool."""

from __future__ import annotations

import asyncio
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class GitTool(BaseTool):
    """Execute git commands."""

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return "Run git commands."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="Git subcommand and arguments (e.g. 'status', 'diff', 'log --oneline -10').",
            ),
            ToolParameter(
                name="cwd",
                type="string",
                description="Working directory for the git command.",
                required=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        command: str = kwargs["command"]
        cwd: str | None = kwargs.get("cwd")

        # Block destructive commands
        blocked = ["push --force", "reset --hard", "clean -f", "branch -D"]
        for b in blocked:
            if b in command:
                return ToolResult(
                    output="",
                    success=False,
                    error=f"Blocked destructive git operation: git {command}. Please confirm explicitly.",
                )

        full_command = f"git {command}"

        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

        output = stdout_text
        if stderr_text:
            output += f"\n{stderr_text}"

        return ToolResult(
            output=output.strip(),
            success=process.returncode == 0,
            error=f"git {command} failed" if process.returncode != 0 else None,
            metadata={"command": full_command, "exit_code": process.returncode or 0},
        )
