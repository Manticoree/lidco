"""File pattern matching tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class GlobTool(BaseTool):
    """Find files by glob pattern."""

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return "Find files by glob pattern."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="pattern",
                type="string",
                description="Glob pattern to match files (e.g. '**/*.py').",
            ),
            ToolParameter(
                name="path",
                type="string",
                description="Directory to search in. Defaults to current directory.",
                required=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        pattern: str = kwargs["pattern"]
        search_dir = Path(kwargs.get("path", ".")).resolve()

        if not search_dir.exists():
            return ToolResult(output="", success=False, error=f"Directory not found: {search_dir}")

        matches = sorted(search_dir.glob(pattern))
        # Filter out common noise
        filtered = [
            m for m in matches
            if not any(
                part.startswith(".")
                or part in ("__pycache__", "node_modules", ".git", "venv", ".venv")
                for part in m.parts
            )
        ]

        if not filtered:
            return ToolResult(output="No files matched the pattern.", metadata={"count": 0})

        # Limit output
        shown = filtered[:500]
        lines = [str(f.relative_to(search_dir)) for f in shown]
        output = "\n".join(lines)
        if len(filtered) > 500:
            output += f"\n\n... and {len(filtered) - 500} more files"

        return ToolResult(output=output, metadata={"count": len(filtered)})
