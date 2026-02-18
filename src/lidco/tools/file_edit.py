"""File editing tool (find and replace)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class FileEditTool(BaseTool):
    """Edit a file by replacing exact string matches."""

    @property
    def name(self) -> str:
        return "file_edit"

    @property
    def description(self) -> str:
        return "Replace exact string in file. old_string must be unique or use replace_all."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to edit.",
            ),
            ToolParameter(
                name="old_string",
                type="string",
                description="The exact string to find and replace.",
            ),
            ToolParameter(
                name="new_string",
                type="string",
                description="The replacement string.",
            ),
            ToolParameter(
                name="replace_all",
                type="boolean",
                description="If true, replace all occurrences.",
                required=False,
                default=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).resolve()
        old_string: str = kwargs["old_string"]
        new_string: str = kwargs["new_string"]
        replace_all: bool = kwargs.get("replace_all", False)

        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {path}")

        content = path.read_text(encoding="utf-8")
        count = content.count(old_string)

        if count == 0:
            return ToolResult(output="", success=False, error="old_string not found in file.")

        if count > 1 and not replace_all:
            return ToolResult(
                output="",
                success=False,
                error=f"old_string found {count} times. Use replace_all=true or provide more context.",
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        path.write_text(new_content, encoding="utf-8")

        return ToolResult(
            output=f"Replaced {count if replace_all else 1} occurrence(s) in {path}",
            metadata={"path": str(path), "replacements": count if replace_all else 1},
        )
