"""Content search tool."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class GrepTool(BaseTool):
    """Search file contents by regex pattern."""

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return "Regex search in files. Returns matches with paths and line numbers."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="pattern",
                type="string",
                description="Regex pattern to search for.",
            ),
            ToolParameter(
                name="path",
                type="string",
                description="File or directory to search in.",
                required=False,
            ),
            ToolParameter(
                name="include",
                type="string",
                description="Glob pattern to filter files (e.g. '*.py').",
                required=False,
            ),
            ToolParameter(
                name="case_insensitive",
                type="boolean",
                description="Case-insensitive search.",
                required=False,
                default=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        pattern_str: str = kwargs["pattern"]
        search_path = Path(kwargs.get("path", ".")).resolve()
        include: str | None = kwargs.get("include")
        case_insensitive: bool = kwargs.get("case_insensitive", False)

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern_str, flags)
        except re.error as e:
            return ToolResult(output="", success=False, error=f"Invalid regex: {e}")

        skip_dirs = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}
        results: list[str] = []
        max_results = 200

        def search_file(file_path: Path) -> None:
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                return
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    rel = file_path.relative_to(search_path) if search_path.is_dir() else file_path
                    results.append(f"{rel}:{i}: {line.rstrip()}")
                    if len(results) >= max_results:
                        return

        if search_path.is_file():
            search_file(search_path)
        elif search_path.is_dir():
            glob_pattern = include or "**/*"
            for file_path in search_path.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                if any(d in file_path.parts for d in skip_dirs):
                    continue
                # Skip binary files
                if file_path.suffix in {".pyc", ".exe", ".dll", ".so", ".png", ".jpg", ".zip"}:
                    continue
                search_file(file_path)
                if len(results) >= max_results:
                    break
        else:
            return ToolResult(output="", success=False, error=f"Path not found: {search_path}")

        if not results:
            return ToolResult(output="No matches found.", metadata={"count": 0})

        output = "\n".join(results)
        if len(results) >= max_results:
            output += f"\n\n(showing first {max_results} results)"

        return ToolResult(output=output, metadata={"count": len(results)})
