"""Tree tool — display directory structure as an indented text tree."""

from __future__ import annotations

import os
from pathlib import Path

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

_MAX_ENTRIES = 200

# Names to always skip regardless of show_hidden
_ALWAYS_SKIP = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"})


class TreeTool(BaseTool):
    """Display a directory structure as an indented text tree.

    Agents use this to get a compact overview of a project or sub-directory
    without reading individual files.  Hidden entries (dotfiles/dotdirs) are
    excluded by default and can be included with ``show_hidden=true``.
    Directories listed in ``_ALWAYS_SKIP`` (e.g. ``.git``, ``__pycache__``)
    are always omitted to keep the output concise.
    """

    @property
    def name(self) -> str:
        return "tree"

    @property
    def description(self) -> str:
        return (
            "Show a directory tree up to max_depth levels deep. "
            "Hidden files and build artifacts are excluded by default."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Root directory to display (default: current working directory).",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="max_depth",
                type="integer",
                description="Maximum depth to traverse (default 3).",
                required=False,
                default=3,
            ),
            ToolParameter(
                name="show_hidden",
                type="boolean",
                description="Include hidden files and directories (default false).",
                required=False,
                default=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(
        self,
        path: str = ".",
        max_depth: int = 3,
        show_hidden: bool = False,
        **_: object,
    ) -> ToolResult:
        root = Path(path).resolve()
        if not root.exists():
            return ToolResult(output="", success=False, error=f"Path not found: {path}")
        if not root.is_dir():
            return ToolResult(output="", success=False, error=f"Not a directory: {path}")

        lines: list[str] = [str(root)]
        entry_count = 0
        truncated = 0

        def _walk(directory: Path, prefix: str, depth: int) -> None:
            nonlocal entry_count, truncated
            if depth > max_depth:
                return

            try:
                entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except PermissionError:
                return

            visible: list[Path] = []
            for entry in entries:
                if entry.name in _ALWAYS_SKIP:
                    continue
                if not show_hidden and entry.name.startswith("."):
                    continue
                visible.append(entry)

            for i, entry in enumerate(visible):
                if entry_count >= _MAX_ENTRIES:
                    truncated += len(visible) - i
                    break

                is_last = i == len(visible) - 1
                connector = "└── " if is_last else "├── "
                suffix = "/" if entry.is_dir() else ""
                lines.append(f"{prefix}{connector}{entry.name}{suffix}")
                entry_count += 1

                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    _walk(entry, prefix + extension, depth + 1)

        _walk(root, "", 1)

        if truncated:
            lines.append(f"... ({truncated} more entries not shown)")

        summary = f"\n{entry_count} entries"
        if truncated:
            summary += f" (+ {truncated} truncated)"

        return ToolResult(
            output="\n".join(lines) + summary,
            success=True,
            metadata={"entry_count": entry_count, "truncated": truncated, "root": str(root)},
        )
