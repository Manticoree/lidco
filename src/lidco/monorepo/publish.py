"""
PublishOrchestrator — manage publish ordering, version bumping, canary versions,
and rollback planning for monorepo packages.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _PkgEntry:
    version: str
    deps: list[str]
    published: bool = False


class PublishOrchestrator:
    """Coordinate publishing of workspace packages in dependency order."""

    def __init__(self) -> None:
        self._packages: dict[str, _PkgEntry] = {}
        self._history: list[dict[str, str]] = []  # snapshots for rollback

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def add_package(
        self,
        name: str,
        version: str = "0.0.0",
        deps: list[str] | None = None,
    ) -> None:
        """Register a package with its current version and workspace deps."""
        self._packages[name] = _PkgEntry(version=version, deps=list(deps or []))

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------

    def publish_order(self) -> list[str]:
        """Return packages in the order they should be published (deps first)."""
        in_deg: dict[str, int] = {n: 0 for n in self._packages}
        dependants: dict[str, list[str]] = {n: [] for n in self._packages}
        for name, entry in self._packages.items():
            for d in entry.deps:
                if d in self._packages:
                    in_deg[name] = in_deg.get(name, 0) + 1
                    dependants.setdefault(d, []).append(name)

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

        for n in sorted(self._packages):
            if n not in result:
                result.append(n)

        return result

    # ------------------------------------------------------------------
    # Version management
    # ------------------------------------------------------------------

    def bump_all(self, bump_type: str = "patch") -> dict[str, str]:
        """Bump all package versions and return {name: new_version}.

        *bump_type* must be ``"major"``, ``"minor"``, or ``"patch"``.
        """
        self._snapshot()
        result: dict[str, str] = {}
        for name, entry in sorted(self._packages.items()):
            entry.version = self._bump_version(entry.version, bump_type)
            result[name] = entry.version
        return result

    def canary_versions(self) -> dict[str, str]:
        """Generate canary (pre-release) versions for every package."""
        ts = str(int(time.time()))
        short_hash = hashlib.md5(ts.encode()).hexdigest()[:7]  # noqa: S324
        result: dict[str, str] = {}
        for name, entry in sorted(self._packages.items()):
            result[name] = f"{entry.version}-canary.{short_hash}"
        return result

    def rollback_plan(self) -> list[dict[str, str]]:
        """Return the version history snapshots (most recent first) for rollback."""
        return list(reversed(self._history))

    def status(self) -> dict[str, Any]:
        """Return a summary dict of all packages and their current state."""
        pkgs: dict[str, dict[str, Any]] = {}
        for name, entry in sorted(self._packages.items()):
            pkgs[name] = {
                "version": entry.version,
                "deps": list(entry.deps),
                "published": entry.published,
            }
        return {
            "total": len(self._packages),
            "packages": pkgs,
            "history_depth": len(self._history),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _snapshot(self) -> None:
        snap = {name: entry.version for name, entry in self._packages.items()}
        self._history.append(snap)

    @staticmethod
    def _bump_version(version: str, bump_type: str) -> str:
        parts = version.split(".")
        if len(parts) != 3:
            parts = ["0", "0", "0"]
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        else:
            patch += 1
        return f"{major}.{minor}.{patch}"
