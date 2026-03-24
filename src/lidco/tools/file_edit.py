"""File editing tool (find and replace)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class FileEditTool(BaseTool):
    """Edit a file by replacing exact string matches."""

    # Task 454: shadow workspace for dry-run mode
    _shadow_workspace: object | None = None

    def set_shadow_workspace(self, sw: object) -> None:
        """Set a ShadowWorkspace instance for dry-run mode (Task 454)."""
        self._shadow_workspace = sw

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

        content = path.read_text(encoding="utf-8", errors="replace")
        count = content.count(old_string)

        if count == 0:
            search_preview = old_string[:80].replace("\n", "↵")
            return ToolResult(
                output="",
                success=False,
                error=(
                    f"old_string not found in file. "
                    f"Searched for: '{search_preview}'. "
                    "Use file_read to verify the exact content first."
                ),
                metadata={"path": str(path), "search_preview": search_preview},
            )

        if count > 1 and not replace_all:
            # Find line numbers of first 3 matches
            match_lines: list[int] = []
            search_pos = 0
            lines_so_far = 0
            for char_idx, ch in enumerate(content):
                if ch == "\n":
                    lines_so_far += 1
                if char_idx == content.find(old_string, search_pos):
                    match_lines.append(lines_so_far + 1)
                    search_pos = char_idx + 1
                    if len(match_lines) >= 3:
                        break
            line_hints = ", ".join(f"line {ln}" for ln in match_lines)
            return ToolResult(
                output="",
                success=False,
                error=(
                    f"old_string found {count} times (at {line_hints}). "
                    "Use replace_all=true to replace all, or add more surrounding context "
                    "to old_string to make it unique."
                ),
                metadata={"path": str(path), "match_count": count, "match_lines": match_lines},
            )

        # Record the anchor line before replacing so we can produce a context preview.
        anchor_offset = content.index(old_string)
        anchor_line = content[:anchor_offset].count("\n")

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        # Task 454: shadow workspace intercept (dry-run mode)
        _sw = self._shadow_workspace
        if _sw is not None and getattr(_sw, "active", False):
            _sw.intercept(str(path), new_content)  # type: ignore[union-attr]
            return ToolResult(
                output=f"[dry-run] Staged edit: {path}",
                success=True,
                metadata={
                    "path": str(path),
                    "dry_run": True,
                    "replacements": count if replace_all else 1,
                },
            )

        path.write_text(new_content, encoding="utf-8")

        _CONTEXT = 10
        lines = new_content.splitlines()
        start = max(0, anchor_line - _CONTEXT)
        end = min(len(lines), anchor_line + _CONTEXT + 1)
        context_preview = "\n".join(lines[start:end])

        return ToolResult(
            output=f"Replaced {count if replace_all else 1} occurrence(s) in {path}",
            metadata={
                "path": str(path),
                "replacements": count if replace_all else 1,
                "anchor_line": anchor_line,
                "context_preview": context_preview,
            },
        )
