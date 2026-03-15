"""Change impact analysis — Task 345."""

from __future__ import annotations

from dataclasses import dataclass, field
from .dependency_graph import DependencyGraph
from .symbol_index import SymbolIndex


@dataclass(frozen=True)
class ImpactedModule:
    module: str
    reason: str   # "direct" | "transitive"
    depth: int    # 1 = direct importer, 2 = transitive, etc.


@dataclass
class ImpactReport:
    changed_modules: list[str]
    impacted: list[ImpactedModule]

    @property
    def direct_count(self) -> int:
        return sum(1 for i in self.impacted if i.reason == "direct")

    @property
    def transitive_count(self) -> int:
        return sum(1 for i in self.impacted if i.reason == "transitive")

    def modules_at_depth(self, depth: int) -> list[str]:
        return [i.module for i in self.impacted if i.depth == depth]


class ChangeImpactAnalyzer:
    """Determine which modules are affected when a set of modules changes."""

    def analyze(
        self,
        changed_modules: list[str],
        graph: DependencyGraph,
        max_depth: int = 10,
    ) -> ImpactReport:
        """Return impact report for the given set of changed modules.

        Uses the *reversed* dependency graph to find who imports the changed modules.
        """
        rev = graph.reverse()
        impacted: dict[str, ImpactedModule] = {}
        queue: list[tuple[str, int]] = []

        for mod in changed_modules:
            for importer in rev.edges.get(mod, set()):
                if importer not in changed_modules and importer not in impacted:
                    entry = ImpactedModule(module=importer, reason="direct", depth=1)
                    impacted[importer] = entry
                    queue.append((importer, 1))

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for importer in rev.edges.get(current, set()):
                if importer not in changed_modules and importer not in impacted:
                    entry = ImpactedModule(
                        module=importer, reason="transitive", depth=depth + 1
                    )
                    impacted[importer] = entry
                    queue.append((importer, depth + 1))

        return ImpactReport(
            changed_modules=list(changed_modules),
            impacted=list(impacted.values()),
        )
