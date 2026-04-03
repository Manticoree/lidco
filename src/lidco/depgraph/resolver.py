"""Version resolver — conflict detection, diamond deps, upgrade suggestions."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.depgraph.builder import DepGraphBuilder


class VersionResolver:
    """Resolve version conflicts in a :class:`DepGraphBuilder` graph."""

    def __init__(self, builder: DepGraphBuilder) -> None:
        self._builder = builder

    # -- conflict detection ------------------------------------------------

    def find_conflicts(self) -> list[dict]:
        """Return nodes whose incoming edges carry conflicting version constraints."""
        target_constraints: dict[str, list[str]] = {}
        for edge in self._builder.all_edges():
            if edge.version_constraint:
                target_constraints.setdefault(edge.target, [])
                target_constraints = {
                    **target_constraints,
                    edge.target: [*target_constraints[edge.target], edge.version_constraint],
                }
        conflicts: list[dict] = []
        for name, constraints in target_constraints.items():
            unique = list(dict.fromkeys(constraints))
            if len(unique) > 1:
                conflicts = [*conflicts, {"name": name, "constraints": unique}]
        return conflicts

    # -- diamond detection -------------------------------------------------

    def find_diamond(self) -> list[dict]:
        """Return diamond dependency patterns (multiple paths to the same target)."""
        # Build adjacency: source -> list[target]
        children: dict[str, list[str]] = {}
        for edge in self._builder.all_edges():
            children.setdefault(edge.source, [])
            children = {
                **children,
                edge.source: [*children[edge.source], edge.target],
            }
        # For each node, collect grandchildren and look for duplicates
        diamonds: list[dict] = []
        for parent, kids in children.items():
            grandchild_sources: dict[str, list[str]] = {}
            for kid in kids:
                for grandchild in children.get(kid, []):
                    grandchild_sources.setdefault(grandchild, [])
                    grandchild_sources = {
                        **grandchild_sources,
                        grandchild: [*grandchild_sources[grandchild], kid],
                    }
            for gc, sources in grandchild_sources.items():
                if len(sources) > 1:
                    diamonds = [
                        *diamonds,
                        {"top": parent, "middle": sources, "bottom": gc},
                    ]
        return diamonds

    # -- upgrade suggestions -----------------------------------------------

    def suggest_upgrades(self) -> list[dict]:
        """Suggest version bumps for every node that has a version string."""
        suggestions: list[dict] = []
        for node in self._builder.all_nodes():
            if not node.version:
                continue
            parts = node.version.split(".")
            try:
                major = int(parts[0])
                minor = int(parts[1]) if len(parts) > 1 else 0
                patch = int(parts[2]) if len(parts) > 2 else 0
            except ValueError:
                continue
            suggested = f"{major}.{minor}.{patch + 1}"
            suggestions = [
                *suggestions,
                {"name": node.name, "current": node.version, "suggested": suggested},
            ]
        return suggestions

    # -- resolution --------------------------------------------------------

    def resolve(self, constraints: list[dict]) -> dict[str, str]:
        """Resolve *constraints* using a simple latest-wins strategy.

        Each constraint dict must have ``name`` and ``version`` keys.
        """
        resolved: dict[str, str] = {}
        for c in constraints:
            name = c["name"]
            version = c["version"]
            if name not in resolved or _version_tuple(version) > _version_tuple(resolved[name]):
                resolved = {**resolved, name: version}
        return resolved


def _version_tuple(v: str) -> tuple[int, ...]:
    """Parse a dotted version string into a comparable tuple."""
    parts: list[int] = []
    for p in v.split("."):
        try:
            parts = [*parts, int(p)]
        except ValueError:
            parts = [*parts, 0]
    return tuple(parts)
