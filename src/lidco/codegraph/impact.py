"""Impact analysis — determine which symbols and files are affected by changes."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from lidco.codegraph.builder import CodeGraphBuilder


@dataclass(frozen=True)
class ImpactResult:
    """Result of an impact analysis."""

    affected: list[str]
    confidence: float
    transitive_count: int


class ImpactAnalyzer:
    """Analyzes the impact of code changes on the graph."""

    def __init__(self, builder: CodeGraphBuilder) -> None:
        self._builder = builder

    def _reverse_reachable(self, names: list[str]) -> list[str]:
        """BFS over reverse edges to find all affected symbols."""
        visited: set[str] = set(names)
        queue: deque[str] = deque(names)
        while queue:
            current = queue.popleft()
            for edge in self._builder.edges():
                if edge.target == current and edge.source not in visited:
                    visited.add(edge.source)
                    queue.append(edge.source)
        # Exclude the seed names themselves from "affected"
        return sorted(visited - set(names))

    def analyze(self, changed_names: list[str]) -> ImpactResult:
        """Return an :class:`ImpactResult` for the given changed symbols."""
        affected = self._reverse_reachable(changed_names)
        total_nodes = len(self._builder.nodes())
        confidence = 1.0 - (len(affected) / max(total_nodes, 1))
        return ImpactResult(
            affected=affected,
            confidence=round(confidence, 4),
            transitive_count=len(affected),
        )

    def affected_files(self, changed_names: list[str]) -> set[str]:
        """Return the set of files containing affected symbols."""
        affected = self._reverse_reachable(changed_names)
        files: set[str] = set()
        for name in affected:
            node = self._builder.get_node(name)
            if node is not None:
                files.add(node.file)
        return files

    def affected_tests(
        self, changed_names: list[str], test_prefix: str = "test_"
    ) -> list[str]:
        """Return affected symbol names that start with *test_prefix*."""
        affected = self._reverse_reachable(changed_names)
        return sorted(n for n in affected if n.startswith(test_prefix))
