"""
DependencyGraphV2 — workspace-level dependency graph with cycle detection,
version consistency checks, unused dep analysis, Mermaid export, and topo sort.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Inconsistency:
    """A version inconsistency record."""

    dependency: str
    versions: dict[str, str]  # package_name -> version_required


class DependencyGraphV2:
    """Workspace dependency graph."""

    def __init__(self) -> None:
        self._packages: dict[str, list[str]] = {}  # name -> dep names
        self._versions: dict[str, dict[str, str]] = {}  # name -> {dep: version}
        self._used_deps: dict[str, set[str]] = {}  # name -> deps actually imported

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def add_package(
        self,
        name: str,
        deps: list[str] | None = None,
        dep_versions: dict[str, str] | None = None,
        used_deps: list[str] | None = None,
    ) -> None:
        """Register a package with optional version map and actually-used deps."""
        self._packages[name] = list(deps or [])
        if dep_versions:
            self._versions[name] = dict(dep_versions)
        if used_deps is not None:
            self._used_deps[name] = set(used_deps)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def detect_circular(self) -> list[list[str]]:
        """Return a list of cycles (each cycle is a list of package names)."""
        cycles: list[list[str]] = []
        visited: set[str] = set()
        on_stack: set[str] = set()
        stack: list[str] = []

        def _dfs(node: str) -> None:
            visited.add(node)
            on_stack.add(node)
            stack.append(node)
            for dep in self._packages.get(node, []):
                if dep not in self._packages:
                    continue
                if dep not in visited:
                    _dfs(dep)
                elif dep in on_stack:
                    # Extract cycle
                    idx = stack.index(dep)
                    cycle = list(stack[idx:]) + [dep]
                    cycles.append(cycle)
            stack.pop()
            on_stack.remove(node)

        for pkg in sorted(self._packages):
            if pkg not in visited:
                _dfs(pkg)

        return cycles

    def version_consistency(self) -> list[Inconsistency]:
        """Check that shared deps use the same version across packages."""
        # dep_name -> {package_name: version_str}
        dep_map: dict[str, dict[str, str]] = {}
        for pkg, versions in self._versions.items():
            for dep, ver in versions.items():
                dep_map.setdefault(dep, {})[pkg] = ver

        results: list[Inconsistency] = []
        for dep_name in sorted(dep_map):
            mapping = dep_map[dep_name]
            unique_versions = set(mapping.values())
            if len(unique_versions) > 1:
                results.append(Inconsistency(dependency=dep_name, versions=dict(mapping)))
        return results

    def unused_deps(self, package: str) -> list[str]:
        """Return declared deps of *package* that are not in its used_deps set."""
        declared = self._packages.get(package, [])
        used = self._used_deps.get(package)
        if used is None:
            return []
        return sorted(d for d in declared if d not in used)

    def as_mermaid(self) -> str:
        """Export the graph as a Mermaid flowchart."""
        lines = ["graph TD"]
        for pkg in sorted(self._packages):
            for dep in sorted(self._packages[pkg]):
                lines.append(f"    {pkg} --> {dep}")
        if len(lines) == 1:
            lines.append("    (empty)")
        return "\n".join(lines)

    def topological_order(self) -> list[str]:
        """Return packages in topological order (leaves/deps first)."""
        # in_deg counts how many deps a package has (within the graph).
        in_deg: dict[str, int] = {n: 0 for n in self._packages}
        # reverse adjacency: dep -> list of dependants
        dependants: dict[str, list[str]] = {n: [] for n in self._packages}
        for name, deps in self._packages.items():
            for d in deps:
                if d in self._packages:
                    in_deg[name] = in_deg.get(name, 0) + 1
                    dependants.setdefault(d, []).append(name)

        # Kahn's algorithm — use sorted queues for determinism.
        queue = sorted(n for n, deg in in_deg.items() if deg == 0)
        result: list[str] = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for dep in dependants.get(node, []):
                if dep in in_deg:
                    in_deg[dep] -= 1
                    if in_deg[dep] == 0:
                        queue.append(dep)
                        queue.sort()

        # Remaining nodes are part of cycles — append sorted.
        for n in sorted(self._packages):
            if n not in result:
                result.append(n)

        return result
