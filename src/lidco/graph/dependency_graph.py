"""AST-based code dependency graph — IMPORTS, CALLS, INHERITS edges (CodeCompass parity)."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict, deque
from typing import Iterator


EdgeKind = str  # "imports" | "calls" | "inherits" | "instantiates"

_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "dist", "build"}


@dataclass
class Edge:
    src: str       # symbol or module name
    dst: str
    kind: EdgeKind
    file: str
    line: int


@dataclass
class GraphStats:
    nodes: int
    edges: int
    most_imported: list[tuple[str, int]]   # (module, count) top 10
    most_called: list[tuple[str, int]]


class DependencyGraph:
    """Build and query a symbol-level dependency graph for a Python codebase.

    Nodes: module names (from file paths) and symbol names (class/function).
    Edges: IMPORTS, CALLS, INHERITS.
    """

    def __init__(self) -> None:
        self._edges: list[Edge] = []
        self._adj: dict[str, list[Edge]] = defaultdict(list)   # src → edges
        self._rev: dict[str, list[Edge]] = defaultdict(list)   # dst → edges

    def add_edge(self, edge: Edge) -> None:
        self._edges.append(edge)
        self._adj[edge.src].append(edge)
        self._rev[edge.dst].append(edge)

    # ── builders ──────────────────────────────────────────────────────

    def build_from_source(self, source: str, module_name: str = "<module>", file: str = "") -> None:
        """Parse source and add edges to the graph."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        # IMPORTS
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.add_edge(Edge(src=module_name, dst=alias.name, kind="imports",
                                       file=file, line=node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.add_edge(Edge(src=module_name, dst=node.module, kind="imports",
                                       file=file, line=node.lineno))

        # INHERITS
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if base_name:
                        self.add_edge(Edge(src=node.name, dst=base_name, kind="inherits",
                                           file=file, line=node.lineno))

        # CALLS (function-level)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                caller = node.name
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        callee = ""
                        if isinstance(child.func, ast.Name):
                            callee = child.func.id
                        elif isinstance(child.func, ast.Attribute):
                            callee = child.func.attr
                        if callee and callee != caller:
                            self.add_edge(Edge(src=caller, dst=callee, kind="calls",
                                               file=file, line=getattr(child, "lineno", 0)))

    def build_from_directory(self, root: str | Path) -> None:
        """Walk a directory and build the full graph."""
        root = Path(root).resolve()
        for path in root.rglob("*.py"):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Module name from relative path
            try:
                rel = path.relative_to(root)
                module = str(rel).replace("\\", "/").replace("/", ".").removesuffix(".py")
            except ValueError:
                module = path.stem
            self.build_from_source(source, module_name=module, file=str(path))

    # ── queries ───────────────────────────────────────────────────────

    def edges_from(self, node: str, kind: EdgeKind | None = None) -> list[Edge]:
        edges = self._adj.get(node, [])
        if kind:
            return [e for e in edges if e.kind == kind]
        return list(edges)

    def edges_to(self, node: str, kind: EdgeKind | None = None) -> list[Edge]:
        edges = self._rev.get(node, [])
        if kind:
            return [e for e in edges if e.kind == kind]
        return list(edges)

    def reachable(self, start: str, kind: EdgeKind | None = None, max_depth: int = 5) -> set[str]:
        """BFS: all nodes reachable from start."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue:
            node, depth = queue.popleft()
            if node in visited or depth > max_depth:
                continue
            visited.add(node)
            for edge in self.edges_from(node, kind):
                if edge.dst not in visited:
                    queue.append((edge.dst, depth + 1))
        visited.discard(start)
        return visited

    def dependents(self, node: str, kind: EdgeKind | None = None, max_depth: int = 5) -> set[str]:
        """BFS: all nodes that depend on (point to) node."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(node, 0)])
        while queue:
            n, depth = queue.popleft()
            if n in visited or depth > max_depth:
                continue
            visited.add(n)
            for edge in self.edges_to(n, kind):
                if edge.src not in visited:
                    queue.append((edge.src, depth + 1))
        visited.discard(node)
        return visited

    def stats(self) -> GraphStats:
        import_counts: dict[str, int] = defaultdict(int)
        call_counts: dict[str, int] = defaultdict(int)
        for e in self._edges:
            if e.kind == "imports":
                import_counts[e.dst] += 1
            elif e.kind == "calls":
                call_counts[e.dst] += 1
        most_imported = sorted(import_counts.items(), key=lambda x: -x[1])[:10]
        most_called = sorted(call_counts.items(), key=lambda x: -x[1])[:10]
        nodes = len(set(e.src for e in self._edges) | set(e.dst for e in self._edges))
        return GraphStats(nodes=nodes, edges=len(self._edges),
                          most_imported=most_imported, most_called=most_called)

    def format_stats(self) -> str:
        s = self.stats()
        lines = [f"Dependency Graph: {s.nodes} nodes, {s.edges} edges"]
        if s.most_imported:
            lines.append("Top imports: " + ", ".join(f"{m}({c})" for m, c in s.most_imported[:5]))
        if s.most_called:
            lines.append("Top called: " + ", ".join(f"{m}({c})" for m, c in s.most_called[:5]))
        return "\n".join(lines)
