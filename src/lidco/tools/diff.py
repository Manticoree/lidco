"""Diff tool — compare two files and return a unified diff."""

from __future__ import annotations

import difflib
from pathlib import Path

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class DiffTool(BaseTool):
    """Compare two files and return a unified diff.

    Uses Python's stdlib ``difflib`` — no external dependencies required.
    Useful for agents that need to understand what changed between two versions
    of a file or compare similar files without reading them in full.
    """

    @property
    def name(self) -> str:
        return "diff"

    @property
    def description(self) -> str:
        return (
            "Compare two files and return a unified diff. "
            "Reports added/removed line counts in metadata."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path_a",
                type="string",
                description="Path to the first (original) file.",
            ),
            ToolParameter(
                name="path_b",
                type="string",
                description="Path to the second (modified) file.",
            ),
            ToolParameter(
                name="unified",
                type="integer",
                description="Lines of context around each change (default 3).",
                required=False,
                default=3,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(
        self,
        path_a: str,
        path_b: str,
        unified: int = 3,
        **_: object,
    ) -> ToolResult:
        try:
            p_a = Path(path_a)
            p_b = Path(path_b)

            if not p_a.exists():
                return ToolResult(output="", success=False, error=f"File not found: {path_a}")
            if not p_b.exists():
                return ToolResult(output="", success=False, error=f"File not found: {path_b}")

            lines_a = p_a.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            lines_b = p_b.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

            diff_lines = list(
                difflib.unified_diff(
                    lines_a,
                    lines_b,
                    fromfile=str(p_a),
                    tofile=str(p_b),
                    n=unified,
                )
            )

            if not diff_lines:
                return ToolResult(
                    output="Files are identical.",
                    success=True,
                    metadata={"added": 0, "removed": 0, "identical": True},
                )

            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

            return ToolResult(
                output="".join(diff_lines),
                success=True,
                metadata={"added": added, "removed": removed, "identical": False},
            )

        except UnicodeDecodeError as e:
            return ToolResult(output="", success=False, error=f"Cannot diff binary file: {e}")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
