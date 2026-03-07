"""Import analyzer tool — detect circular imports and analyze dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lidco.core.import_graph import build_graph
from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class ImportAnalyzerTool(BaseTool):
    """Analyze Python import dependencies and detect circular imports.

    Scans all ``.py`` files in the given directory using AST analysis (no
    subprocess required).  Reports:

    - Total files scanned and import counts
    - Internal vs external import breakdown
    - Any circular import chains
    """

    @property
    def name(self) -> str:
        return "analyze_imports"

    @property
    def description(self) -> str:
        return (
            "Analyze Python import dependencies and detect circular imports. "
            "Uses AST analysis — no subprocess needed."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description=(
                    "Directory to analyze. Defaults to current working directory."
                ),
                required=False,
                default=".",
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        path_str: str = kwargs.get("path", ".")
        root = Path(path_str).resolve()

        if not root.exists():
            return ToolResult(
                output=f"Path not found: {path_str}",
                success=False,
                error=f"Path not found: {path_str}",
            )

        if not root.is_dir():
            root = root.parent

        graph = build_graph(root)
        # find_cycles() is also called inside summary() — compute once and reuse.
        cycles = graph.find_cycles()
        summary = graph.summary(_precomputed_cycles=cycles)

        return ToolResult(
            output=summary,
            success=(len(cycles) == 0),
            metadata={
                "cycles": cycles,
                "cycle_count": len(cycles),
                "total_imports": len(graph.edges),
                "files": len(graph.get_files()),
            },
        )
