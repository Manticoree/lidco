"""Cross-repo / cross-package dependency graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.workspace.detector import PackageInfo


@dataclass
class DepGraph:
    """A directed dependency graph."""

    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)

    # -- queries -------------------------------------------------------------

    def find_circular(self) -> list[list[str]]:
        """Return all elementary cycles (simple cycles) in the graph."""
        adj: dict[str, list[str]] = {n: [] for n in self.nodes}
        for src, dst in self.edges:
            if src in adj:
                adj[src].append(dst)

        cycles: list[list[str]] = []
        visited: set[str] = set()

        def _dfs(node: str, path: list[str], on_stack: set[str]) -> None:
            visited.add(node)
            on_stack.add(node)
            path.append(node)
            for nb in adj.get(node, []):
                if nb in on_stack:
                    idx = path.index(nb)
                    cycle = path[idx:]
                    # normalise so that we can dedup
                    normalised = self._normalise_cycle(cycle)
                    if normalised not in cycles:
                        cycles.append(normalised)
                elif nb not in visited:
                    _dfs(nb, path, on_stack)
            path.pop()
            on_stack.discard(node)

        for n in self.nodes:
            if n not in visited:
                _dfs(n, [], set())

        return cycles

    def affected_by(self, package_name: str) -> list[str]:
        """Return all nodes that transitively depend on *package_name*."""
        # Build reverse adjacency
        rev: dict[str, list[str]] = {n: [] for n in self.nodes}
        for src, dst in self.edges:
            if dst in rev:
                rev[dst].append(src)

        visited: set[str] = set()
        queue = [package_name]
        while queue:
            current = queue.pop(0)
            for nb in rev.get(current, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        return sorted(visited)

    def render(self) -> str:
        """Return an ASCII tree representation of the graph."""
        if not self.nodes:
            return "(empty graph)"

        adj: dict[str, list[str]] = {n: [] for n in self.nodes}
        for src, dst in self.edges:
            if src in adj:
                adj[src].append(dst)

        # Find roots (nodes with no incoming edges)
        has_incoming = {dst for _, dst in self.edges}
        roots = [n for n in self.nodes if n not in has_incoming]
        if not roots:
            roots = [self.nodes[0]]

        lines: list[str] = []
        rendered: set[str] = set()

        def _render_node(node: str, prefix: str, is_last: bool) -> None:
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{node}")
            rendered.add(node)
            children = sorted(adj.get(node, []))
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(children):
                if child in rendered:
                    is_child_last = i == len(children) - 1
                    child_conn = "└── " if is_child_last else "├── "
                    lines.append(f"{child_prefix}{child_conn}{child} (cycle)")
                else:
                    _render_node(child, child_prefix, i == len(children) - 1)

        for i, root in enumerate(sorted(roots)):
            if root in rendered:
                continue
            lines.append(root)
            rendered.add(root)
            children = sorted(adj.get(root, []))
            for j, child in enumerate(children):
                if child in rendered:
                    is_child_last = j == len(children) - 1
                    child_conn = "└── " if is_child_last else "├── "
                    lines.append(f"    {child_conn}{child} (cycle)")
                else:
                    _render_node(child, "    ", j == len(children) - 1)

        return "\n".join(lines)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _normalise_cycle(cycle: list[str]) -> list[str]:
        """Rotate cycle so the smallest element comes first."""
        if not cycle:
            return cycle
        min_idx = cycle.index(min(cycle))
        return cycle[min_idx:] + cycle[:min_idx]


class CrossRepoDeps:
    """Build a dependency graph from a list of PackageInfo."""

    def build_graph(self, packages: list[PackageInfo]) -> DepGraph:
        known_names = {p.name for p in packages}
        nodes = sorted(known_names)
        edges: list[tuple[str, str]] = []
        for pkg in packages:
            for dep in pkg.deps:
                if dep in known_names:
                    edges.append((pkg.name, dep))
        return DepGraph(nodes=nodes, edges=sorted(set(edges)))
