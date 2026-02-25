"""Architecture diagram tool — ASCII import-dependency graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class ArchDiagramTool(BaseTool):
    """Render an ASCII import-dependency graph for a module or directory."""

    @property
    def name(self) -> str:
        return "arch_diagram"

    @property
    def description(self) -> str:
        return (
            "Render an ASCII dependency diagram showing which modules import "
            "a given file (dependents) or which modules it imports (dependencies). "
            "Requires the project index to be built (/index)."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="root_path",
                type="string",
                description=(
                    "File or directory to analyse "
                    "(relative path, e.g. 'src/lidco/core/session.py'). "
                    "Empty = top-level import summary."
                ),
                required=False,
                default="",
            ),
            ToolParameter(
                name="direction",
                type="string",
                description=(
                    "'dependencies' = what this module imports, "
                    "'dependents' = what imports this module, "
                    "'both' = both directions."
                ),
                required=False,
                default="both",
            ),
            ToolParameter(
                name="max_depth",
                type="integer",
                description="Maximum depth of the dependency tree to render.",
                required=False,
                default=2,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        root_path: str = kwargs.get("root_path", "")
        direction: str = kwargs.get("direction", "both").lower()
        max_depth: int = int(kwargs.get("max_depth", 2))

        if direction not in ("dependencies", "dependents", "both"):
            return ToolResult(
                output="",
                success=False,
                error="direction must be 'dependencies', 'dependents', or 'both'.",
            )

        cwd = Path.cwd()
        db_path = cwd / ".lidco" / "project_index.db"
        if not db_path.exists():
            return ToolResult(
                output="",
                success=False,
                error=(
                    "Project index not found. Run `/index` first to build the "
                    "structural index, then try again."
                ),
            )

        try:
            from lidco.index.db import IndexDatabase
            from lidco.index.dependency_graph import DependencyGraph

            db = IndexDatabase(db_path)
            try:
                graph = DependencyGraph(db)
                output = _render_diagram(graph, root_path, direction, max_depth)
            finally:
                db.close()
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Index error: {e}")

        return ToolResult(
            output=output,
            success=True,
            metadata={"root_path": root_path, "direction": direction, "max_depth": max_depth},
        )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_diagram(
    graph: Any,
    root_path: str,
    direction: str,
    max_depth: int,
) -> str:
    """Build the ASCII dependency tree string."""
    graph._ensure_built()

    if not root_path:
        return _render_top_level_summary(graph)

    lines: list[str] = [f"## Dependency diagram: `{root_path}`\n"]

    if direction in ("dependents", "both"):
        dependents = _build_tree(
            graph._imported_by, root_path, max_depth, set()
        )
        if dependents:
            lines.append("### Dependents (files that import this module)")
            lines.extend(dependents)
        else:
            lines.append("### Dependents — none found")
        lines.append("")

    if direction in ("dependencies", "both"):
        deps = _build_tree(
            graph._imports, root_path, max_depth, set()
        )
        if deps:
            lines.append("### Dependencies (modules imported by this file)")
            lines.extend(deps)
        else:
            lines.append("### Dependencies — none found")
        lines.append("")

    return "\n".join(lines)


def _build_tree(
    adj: dict[str, set[str]],
    node: str,
    max_depth: int,
    visited: set[str],
    prefix: str = "",
    depth: int = 0,
) -> list[str]:
    """Recursively build indented tree lines."""
    if depth >= max_depth:
        return []
    children = sorted(adj.get(node, set()))
    lines: list[str] = []
    for i, child in enumerate(children):
        is_last = i == len(children) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{child}")
        if child not in visited:
            new_visited = visited | {child}
            extension = "    " if is_last else "│   "
            lines.extend(
                _build_tree(adj, child, max_depth, new_visited, prefix + extension, depth + 1)
            )
    return lines


def _render_top_level_summary(graph: Any) -> str:
    """Show most-imported and most-depended-upon modules."""
    graph._ensure_built()

    # Most imported (most dependents)
    by_dependents = sorted(
        ((path, len(deps)) for path, deps in graph._imported_by.items() if deps),
        key=lambda x: -x[1],
    )[:15]

    # Most dependencies
    by_deps = sorted(
        ((path, len(deps)) for path, deps in graph._imports.items() if deps),
        key=lambda x: -x[1],
    )[:15]

    lines = ["## Architecture Overview\n"]

    if by_dependents:
        lines.append("### Most imported modules")
        for path, count in by_dependents:
            lines.append(f"  {count:3d}×  {path}")
        lines.append("")

    if by_deps:
        lines.append("### Most dependencies")
        for path, count in by_deps:
            lines.append(f"  {count:3d} deps  {path}")
        lines.append("")

    if not by_dependents and not by_deps:
        lines.append("_No import relationships found. Run `/index` to build the project index._")

    return "\n".join(lines)
