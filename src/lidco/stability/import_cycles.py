"""
Import cycle detector — Q339.

Builds a dependency graph from module imports and detects cycles using DFS,
then suggests refactoring to break them.
"""
from __future__ import annotations


class ImportCycleDetector:
    """Detect import cycles in a Python project's dependency graph."""

    def __init__(self) -> None:
        # Adjacency list: module -> list of modules it imports.
        self._graph: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_graph(self, modules: dict[str, list[str]]) -> dict:
        """Build dependency graph from *modules* mapping (module -> imports).

        Returns the adjacency dict (also stored internally).
        """
        self._graph = {mod: list(deps) for mod, deps in modules.items()}
        # Ensure every referenced node exists in the graph.
        for deps in list(self._graph.values()):
            for dep in deps:
                if dep not in self._graph:
                    self._graph[dep] = []
        return dict(self._graph)

    def detect_cycles(self) -> list[list[str]]:
        """Find all cycles in the dependency graph using iterative DFS.

        Returns a list of cycles; each cycle is an ordered list of module names
        that forms a closed loop (the first element is repeated at the end is
        NOT included — the cycle is implied).
        """
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbour in self._graph.get(node, []):
                if neighbour not in visited:
                    dfs(neighbour, path)
                elif neighbour in rec_stack:
                    # Extract the cycle portion of the current path.
                    cycle_start = path.index(neighbour)
                    cycle = path[cycle_start:]
                    # Avoid duplicate cycles (same node set, different start).
                    normalised = tuple(sorted(cycle))
                    if not any(tuple(sorted(c)) == normalised for c in cycles):
                        cycles.append(list(cycle))

            path.pop()
            rec_stack.discard(node)

        for node in list(self._graph.keys()):
            if node not in visited:
                dfs(node, [])

        return cycles

    def suggest_breaks(self, cycles: list[list[str]]) -> list[dict]:
        """Suggest how to break each cycle.

        Returns dicts with "cycle", "suggestion", "break_point".
        """
        results: list[dict] = []

        for cycle in cycles:
            if not cycle:
                continue

            # Heuristic: choose the module with the highest number of imports
            # (most depended-upon) as the break point — extracting an interface
            # there removes the most coupling.
            best_break = max(
                cycle, key=lambda m: len(self._graph.get(m, []))
            )

            results.append(
                {
                    "cycle": cycle,
                    "suggestion": (
                        f"Extract the shared interface from '{best_break}' into a "
                        "new 'protocols' or 'interfaces' module that neither side "
                        "of the cycle needs to import from each other directly. "
                        "Alternatively, use lazy imports (import inside function body) "
                        "to defer the import until runtime."
                    ),
                    "break_point": best_break,
                }
            )

        return results

    def lazy_import_helper(self, module_name: str) -> str:
        """Generate a lazy import code snippet for *module_name*.

        Returns a string containing Python code that defers the import.
        """
        return (
            f"def _import_{module_name.replace('.', '_')}():\n"
            f"    \"\"\"Lazy import for '{module_name}' to break import cycles.\"\"\"\n"
            f"    import {module_name}  # noqa: PLC0415\n"
            f"    return {module_name}\n"
        )
