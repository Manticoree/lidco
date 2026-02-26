"""Git operations tool."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


def _classify_git_error(stderr: str) -> str | None:
    """Return a short error-type label from git stderr output, or None."""
    text = stderr.lower()
    if "not a git repository" in text:
        return "not_a_git_repo"
    if "merge conflict" in text or "automatic merge failed" in text:
        return "merge_conflict"
    if "already exists" in text:
        return "already_exists"
    if "did not match any" in text or "unknown revision" in text or "pathspec" in text:
        return "not_found"
    if "permission denied" in text:
        return "permission_denied"
    if "nothing to commit" in text or "nothing added to commit" in text:
        return "nothing_to_commit"
    return None


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

        try:
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        except asyncio.TimeoutError:
            process.kill()
            return ToolResult(
                output="",
                success=False,
                error=f"git {command} timed out after 60s",
                metadata={"command": full_command, "exit_code": -1},
            )
        except Exception as exc:
            return ToolResult(
                output="",
                success=False,
                error=f"git {command} failed: {exc}",
                metadata={"command": full_command, "exit_code": -1},
            )

        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

        output = stdout_text
        if stderr_text:
            output += f"\n{stderr_text}"

        rc = process.returncode or 0
        error_msg: str | None = None
        git_error_type: str | None = None
        if rc != 0:
            stderr_summary = stderr_text.strip()[:300]
            git_error_type = _classify_git_error(stderr_text)
            error_msg = f"git {command} failed"
            if stderr_summary:
                error_msg += f": {stderr_summary}"

        return ToolResult(
            output=output.strip(),
            success=rc == 0,
            error=error_msg,
            metadata={
                "command": full_command,
                "exit_code": rc,
                **({"git_error_type": git_error_type} if git_error_type else {}),
            },
        )
