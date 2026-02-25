"""Multi-file symbol rename tool."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class RenameSymbolTool(BaseTool):
    """Rename a symbol (class, function, variable) across multiple files."""

    @property
    def name(self) -> str:
        return "rename_symbol"

    @property
    def description(self) -> str:
        return (
            "Find and rename a symbol (class, function, variable) across multiple files. "
            "Supports whole-word matching and dry-run preview mode."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="old_name",
                type="string",
                description="The current symbol name to rename.",
            ),
            ToolParameter(
                name="new_name",
                type="string",
                description="The replacement name.",
            ),
            ToolParameter(
                name="glob_pattern",
                type="string",
                description="Glob pattern for files to search (e.g. '**/*.py').",
                required=False,
                default="**/*.py",
            ),
            ToolParameter(
                name="whole_word",
                type="boolean",
                description=(
                    "Only match whole-word occurrences (default True). "
                    "Set False to replace substrings."
                ),
                required=False,
                default=True,
            ),
            ToolParameter(
                name="dry_run",
                type="boolean",
                description="Preview changes without modifying any files.",
                required=False,
                default=False,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        old_name: str = kwargs.get("old_name", "").strip()
        new_name: str = kwargs.get("new_name", "").strip()
        glob_pattern: str = kwargs.get("glob_pattern", "**/*.py")
        whole_word: bool = bool(kwargs.get("whole_word", True))
        dry_run: bool = bool(kwargs.get("dry_run", False))

        if not old_name or not new_name:
            return ToolResult(
                output="", success=False, error="old_name and new_name are required."
            )
        if old_name == new_name:
            return ToolResult(
                output="old_name and new_name are the same — nothing to do.",
                success=True,
            )

        pattern = re.compile(
            r"\b" + re.escape(old_name) + r"\b" if whole_word else re.escape(old_name)
        )

        cwd = Path.cwd()
        changed: list[dict[str, Any]] = []
        total_replacements = 0

        for file_path in sorted(cwd.glob(glob_pattern)):
            if not file_path.is_file():
                continue
            try:
                original = file_path.read_text(encoding="utf-8")
            except OSError:
                continue

            # Fast pre-check before regex
            if old_name not in original:
                continue

            matches = pattern.findall(original)
            if not matches:
                continue

            new_content = pattern.sub(new_name, original)
            orig_lines = original.splitlines()
            new_lines = new_content.splitlines()
            lines_changed = [
                i + 1
                for i, (a, b) in enumerate(zip(orig_lines, new_lines))
                if a != b
            ]

            changed.append(
                {
                    "path": str(file_path.relative_to(cwd)),
                    "replacements": len(matches),
                    "lines": lines_changed[:5],
                }
            )
            total_replacements += len(matches)

            if not dry_run:
                file_path.write_text(new_content, encoding="utf-8")

        if not changed:
            return ToolResult(
                output=(
                    f"No occurrences of `{old_name}` found "
                    f"matching pattern `{glob_pattern}`."
                ),
                success=True,
                metadata={"total_files": 0, "total_replacements": 0},
            )

        mode = "Would change" if dry_run else "Changed"
        rpl = total_replacements
        fls = len(changed)
        header = (
            f"{mode} `{old_name}` → `{new_name}` "
            f"({rpl} occurrence{'s' if rpl != 1 else ''} "
            f"across {fls} file{'s' if fls != 1 else ''}):\n"
        )
        file_lines: list[str] = []
        for f in changed:
            line_info = (
                f" (lines {', '.join(str(ln) for ln in f['lines'][:3])})"
                if f["lines"]
                else ""
            )
            cnt = f["replacements"]
            file_lines.append(
                f"  {f['path']} — {cnt} replacement{'s' if cnt != 1 else ''}{line_info}"
            )

        output = header + "\n".join(file_lines)
        if dry_run:
            output += "\n\n_Dry run — no files modified._"

        return ToolResult(
            output=output,
            success=True,
            metadata={
                "total_files": fls,
                "total_replacements": total_replacements,
                "dry_run": dry_run,
                "changed_files": [f["path"] for f in changed],
            },
        )
