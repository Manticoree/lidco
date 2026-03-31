"""Change impact analysis — Q126."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.analysis.python_extractor import ExtractionResult


@dataclass
class ImpactReport:
    changed_file: str
    directly_affected: list[str] = field(default_factory=list)
    transitively_affected: list[str] = field(default_factory=list)

    @property
    def total_affected(self) -> int:
        return len(self.directly_affected) + len(self.transitively_affected)


class ChangeImpactAnalyzer:
    """Determine which modules are affected when a module changes."""

    def __init__(self, import_graph: dict[str, list[str]] = None) -> None:
        # import_graph: {module: [imported_modules]}
        self._graph: dict[str, list[str]] = dict(import_graph) if import_graph else {}

    def add_import(self, module: str, imports: str) -> None:
        if module not in self._graph:
            self._graph[module] = []
        if imports not in self._graph[module]:
            self._graph[module].append(imports)

    def build_from_extractor(self, results: list) -> None:
        """Build graph from a list of ExtractionResult objects."""
        for r in results:
            self._graph[r.module] = list(r.imports)

    def reverse_graph(self) -> dict[str, list[str]]:
        """Return {module: [modules_that_import_it]}."""
        rev: dict[str, list[str]] = {}
        for mod, imports in self._graph.items():
            for imp in imports:
                rev.setdefault(imp, []).append(mod)
        return rev

    def analyze(self, changed_module: str) -> ImpactReport:
        rev = self.reverse_graph()
        directly = list(rev.get(changed_module, []))
        visited = set(directly)
        queue = list(directly)
        transitively: list[str] = []
        while queue:
            current = queue.pop(0)
            for importer in rev.get(current, []):
                if importer not in visited and importer != changed_module:
                    visited.add(importer)
                    transitively.append(importer)
                    queue.append(importer)
        return ImpactReport(
            changed_file=changed_module,
            directly_affected=directly,
            transitively_affected=transitively,
        )
