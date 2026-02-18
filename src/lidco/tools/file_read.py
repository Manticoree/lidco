"""File reading tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class FileReadTool(BaseTool):
    """Read file contents."""

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read file with line numbers."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Absolute or relative path to the file to read.",
            ),
            ToolParameter(
                name="offset",
                type="integer",
                description="Line number to start reading from (1-based).",
                required=False,
                default=1,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of lines to read.",
                required=False,
                default=2000,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).resolve()
        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit", 2000)

        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {path}")

        if not path.is_file():
            return ToolResult(output="", success=False, error=f"Not a file: {path}")

        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = max(0, offset - 1)
        end = start + limit
        selected = lines[start:end]

        numbered = [f"{start + i + 1:>6}\t{line}" for i, line in enumerate(selected)]
        output = "\n".join(numbered)

        return ToolResult(
            output=output,
            metadata={"path": str(path), "total_lines": len(lines), "shown": len(selected)},
        )
