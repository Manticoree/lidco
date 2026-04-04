"""
PackageDetector — detect monorepo tooling and enumerate workspace packages.

Supports: Nx, Turborepo, Lerna, pnpm workspaces.
No network calls — pure filesystem inspection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Package:
    """A single workspace package."""

    name: str
    path: str
    version: str = "0.0.0"
    private: bool = False
    dependencies: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MonorepoInfo:
    """Aggregate result of monorepo detection."""

    tool: str | None
    root: str
    packages: list[Package]
    workspace_config: dict[str, Any]


class PackageDetector:
    """Detect monorepo tool, enumerate packages, read workspace config."""

    # Marker files for each supported tool (checked in priority order).
    _TOOL_MARKERS: list[tuple[str, str]] = [
        ("nx.json", "nx"),
        ("turbo.json", "turbo"),
        ("lerna.json", "lerna"),
        ("pnpm-workspace.yaml", "pnpm"),
    ]

    def detect_tool(self, root: str) -> str | None:
        """Return the monorepo tool name or *None* if none is detected."""
        root_path = Path(root)
        for marker_file, tool_name in self._TOOL_MARKERS:
            if (root_path / marker_file).exists():
                return tool_name
        return None

    def find_packages(self, root: str) -> list[Package]:
        """Walk the workspace and return every detected package."""
        root_path = Path(root)
        packages: list[Package] = []

        # Strategy: look for package.json or pyproject.toml in immediate children
        # of common workspace dirs, or use globs from workspace config.
        globs = self._workspace_globs(root_path)
        if not globs:
            # Fallback: packages/* and apps/*
            globs = ["packages/*", "apps/*"]

        seen: set[str] = set()
        for pattern in globs:
            for candidate in sorted(root_path.glob(pattern)):
                if not candidate.is_dir():
                    continue
                pkg = self._read_package(candidate)
                if pkg is not None and pkg.name not in seen:
                    seen.add(pkg.name)
                    packages.append(pkg)

        return packages

    def workspace_config(self, root: str) -> dict[str, Any]:
        """Return the raw workspace / tool config as a dict."""
        root_path = Path(root)

        # Nx
        nx_path = root_path / "nx.json"
        if nx_path.exists():
            return self._load_json(nx_path)

        # Turbo
        turbo_path = root_path / "turbo.json"
        if turbo_path.exists():
            return self._load_json(turbo_path)

        # Lerna
        lerna_path = root_path / "lerna.json"
        if lerna_path.exists():
            return self._load_json(lerna_path)

        # pnpm — yaml file, return minimal dict
        pnpm_path = root_path / "pnpm-workspace.yaml"
        if pnpm_path.exists():
            text = pnpm_path.read_text(encoding="utf-8")
            return {"tool": "pnpm", "raw": text}

        return {}

    def detect(self, root: str) -> MonorepoInfo:
        """Full detection: tool + packages + config."""
        tool = self.detect_tool(root)
        packages = self.find_packages(root)
        config = self.workspace_config(root)
        return MonorepoInfo(
            tool=tool,
            root=root,
            packages=packages,
            workspace_config=config,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _workspace_globs(self, root_path: Path) -> list[str]:
        """Extract workspace glob patterns from root package.json."""
        pkg_json = root_path / "package.json"
        if pkg_json.exists():
            data = self._load_json(pkg_json)
            workspaces = data.get("workspaces", [])
            # workspaces can be a list or {"packages": [...]}
            if isinstance(workspaces, dict):
                workspaces = workspaces.get("packages", [])
            if isinstance(workspaces, list):
                return list(workspaces)
        return []

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _read_package(directory: Path) -> Package | None:
        """Try to read a Package from a directory's package.json."""
        pkg_json = directory / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
            name = data.get("name", directory.name)
            version = data.get("version", "0.0.0")
            private = data.get("private", False)
            deps = sorted(
                set(list(data.get("dependencies", {}).keys())
                    + list(data.get("devDependencies", {}).keys()))
            )
            return Package(
                name=name,
                path=str(directory),
                version=version,
                private=private,
                dependencies=deps,
            )
        return None
