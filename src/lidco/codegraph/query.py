"""Graph query engine — callers, callees, transitive deps, BFS path, regex search."""
from __future__ import annotations

import re
from collections import deque

from lidco.codegraph.builder import CodeGraphBuilder, GraphNode


class GraphQueryEngine:
    """Queries over a :class:`CodeGraphBuilder` graph."""

    def __init__(self, builder: CodeGraphBuilder) -> None:
        self._builder = builder

    def callers_of(self, name: str) -> list[str]:
        """Return names of nodes that have an edge targeting *name*."""
        return [e.source for e in self._builder.edges() if e.target == name]

    def callees_of(self, name: str) -> list[str]:
        """Return names of nodes called by *name*."""
        return [e.target for e in self._builder.edges() if e.source == name]

    def depends_on(self, name: str) -> list[str]:
        """Return transitive dependencies of *name* (BFS over outgoing edges)."""
        visited: set[str] = set()
        queue: deque[str] = deque([name])
        while queue:
            current = queue.popleft()
            for edge in self._builder.edges():
                if edge.source == current and edge.target not in visited:
                    visited.add(edge.target)
                    queue.append(edge.target)
        return sorted(visited)

    def path(self, source: str, target: str) -> list[str] | None:
        """Return shortest path from *source* to *target* via BFS, or None."""
        if source == target:
            return [source]
        visited: set[str] = {source}
        queue: deque[list[str]] = deque([[source]])
        while queue:
            current_path = queue.popleft()
            current = current_path[-1]
            for edge in self._builder.edges():
                if edge.source == current and edge.target not in visited:
                    new_path = [*current_path, edge.target]
                    if edge.target == target:
                        return new_path
                    visited.add(edge.target)
                    queue.append(new_path)
        return None

    def search(self, pattern: str) -> list[GraphNode]:
        """Return nodes whose name matches *pattern* (regex)."""
        compiled = re.compile(pattern)
        return [n for n in self._builder.nodes() if compiled.search(n.name)]
