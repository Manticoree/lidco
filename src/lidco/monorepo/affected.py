"""
AffectedFinder — determine which packages are affected by a set of changed files.

Provides transitive dependency analysis and optimized test/build ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class _PkgInfo:
    path: str
    deps: list[str]


class AffectedFinder:
    """Build a package graph, then query which packages are affected by file changes."""

    def __init__(self) -> None:
        self._packages: dict[str, _PkgInfo] = {}

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_package(self, name: str, path: str, deps: list[str] | None = None) -> None:
        """Register a workspace package with its filesystem *path* and direct *deps*."""
        self._packages[name] = _PkgInfo(path=path, deps=list(deps or []))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_affected(self, changed_files: list[str]) -> list[str]:
        """Return package names whose files or transitive dependants are affected.

        A package is *directly* affected when any changed file starts with its path.
        A package is *transitively* affected when it depends on a directly affected
        package (recursively).
        """
        directly: set[str] = set()
        for name, info in self._packages.items():
            normalized = info.path.replace("\\", "/").rstrip("/") + "/"
            for f in changed_files:
                nf = f.replace("\\", "/")
                if nf.startswith(normalized) or nf == normalized.rstrip("/"):
                    directly.add(name)
                    break

        # Expand transitively: any package that depends on an affected one is also affected.
        affected: set[str] = set(directly)
        changed = True
        while changed:
            changed = False
            for name, info in self._packages.items():
                if name in affected:
                    continue
                if any(d in affected for d in info.deps):
                    affected.add(name)
                    changed = True

        return sorted(affected)

    def transitive_deps(self, package: str) -> set[str]:
        """Return the full set of transitive dependencies for *package*."""
        result: set[str] = set()
        stack = list(self._packages.get(package, _PkgInfo("", [])).deps)
        while stack:
            dep = stack.pop()
            if dep in result:
                continue
            result.add(dep)
            if dep in self._packages:
                stack.extend(self._packages[dep].deps)
        return result

    def optimize_test(self, affected: list[str]) -> list[str]:
        """Return *affected* packages in test order (leaf deps first)."""
        return self._topo_sort(affected)

    def optimize_build(self, affected: list[str]) -> list[str]:
        """Return *affected* packages in build order (leaf deps first)."""
        return self._topo_sort(affected)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _topo_sort(self, names: list[str]) -> list[str]:
        """Topological sort of *names* based on dependency edges."""
        name_set = set(names)
        # in-degree within the subset
        in_deg: dict[str, int] = {n: 0 for n in names}
        for n in names:
            info = self._packages.get(n)
            if info:
                for d in info.deps:
                    if d in name_set:
                        in_deg[n] = in_deg.get(n, 0) + 1

        queue = sorted(n for n in names if in_deg[n] == 0)
        result: list[str] = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            # decrement in-degree of dependants
            for n in names:
                info = self._packages.get(n)
                if info and node in info.deps and n in in_deg:
                    in_deg[n] -= 1
                    if in_deg[n] == 0:
                        queue.append(n)
                        queue.sort()

        # append any remaining (cycles)
        for n in sorted(names):
            if n not in result:
                result.append(n)

        return result
