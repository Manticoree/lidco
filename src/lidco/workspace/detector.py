"""Workspace type detection for monorepo and multi-repo setups."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class PackageInfo:
    """Information about a single package in a workspace."""

    name: str
    path: str
    deps: list[str] = field(default_factory=list)


@dataclass
class WorkspaceInfo:
    """Result of workspace detection."""

    workspace_type: str
    packages: list[PackageInfo]
    root: str


class WorkspaceDetector:
    """Detect workspace type (nx, turborepo, lerna, cargo, go, pnpm, yarn, pip, unknown)."""

    def detect(self, root_path: str) -> WorkspaceInfo:
        """Detect workspace type and enumerate packages under *root_path*."""
        root_path = os.path.abspath(root_path)

        # Order matters: more specific first
        detectors = [
            self._detect_nx,
            self._detect_turborepo,
            self._detect_lerna,
            self._detect_cargo,
            self._detect_go,
            self._detect_pnpm,
            self._detect_yarn,
            self._detect_pip,
        ]

        for detector in detectors:
            result = detector(root_path)
            if result is not None:
                return result

        return WorkspaceInfo(workspace_type="unknown", packages=[], root=root_path)

    # -- individual detectors ------------------------------------------------

    def _detect_nx(self, root: str) -> WorkspaceInfo | None:
        nx_json = os.path.join(root, "nx.json")
        if not os.path.isfile(nx_json):
            return None
        packages = self._scan_node_packages(root)
        return WorkspaceInfo(workspace_type="nx", packages=packages, root=root)

    def _detect_turborepo(self, root: str) -> WorkspaceInfo | None:
        turbo_json = os.path.join(root, "turbo.json")
        if not os.path.isfile(turbo_json):
            return None
        packages = self._scan_node_packages(root)
        return WorkspaceInfo(workspace_type="turborepo", packages=packages, root=root)

    def _detect_lerna(self, root: str) -> WorkspaceInfo | None:
        lerna_json = os.path.join(root, "lerna.json")
        if not os.path.isfile(lerna_json):
            return None
        packages = self._scan_node_packages(root)
        return WorkspaceInfo(workspace_type="lerna", packages=packages, root=root)

    def _detect_cargo(self, root: str) -> WorkspaceInfo | None:
        cargo_toml = os.path.join(root, "Cargo.toml")
        if not os.path.isfile(cargo_toml):
            return None
        try:
            text = self._read_text(cargo_toml)
        except OSError:
            return None
        if "[workspace]" not in text:
            return None
        packages = self._parse_cargo_workspace(root, text)
        return WorkspaceInfo(workspace_type="cargo", packages=packages, root=root)

    def _detect_go(self, root: str) -> WorkspaceInfo | None:
        go_work = os.path.join(root, "go.work")
        if not os.path.isfile(go_work):
            return None
        try:
            text = self._read_text(go_work)
        except OSError:
            return None
        packages = self._parse_go_work(root, text)
        return WorkspaceInfo(workspace_type="go", packages=packages, root=root)

    def _detect_pnpm(self, root: str) -> WorkspaceInfo | None:
        pnpm_ws = os.path.join(root, "pnpm-workspace.yaml")
        if not os.path.isfile(pnpm_ws):
            return None
        packages = self._scan_node_packages(root)
        return WorkspaceInfo(workspace_type="pnpm", packages=packages, root=root)

    def _detect_yarn(self, root: str) -> WorkspaceInfo | None:
        pkg_json = os.path.join(root, "package.json")
        if not os.path.isfile(pkg_json):
            return None
        try:
            data = json.loads(self._read_text(pkg_json))
        except (OSError, json.JSONDecodeError):
            return None
        if "workspaces" not in data:
            return None
        packages = self._scan_node_packages(root)
        return WorkspaceInfo(workspace_type="yarn", packages=packages, root=root)

    def _detect_pip(self, root: str) -> WorkspaceInfo | None:
        setup_cfg = os.path.join(root, "setup.cfg")
        pyproject = os.path.join(root, "pyproject.toml")
        if not (os.path.isfile(setup_cfg) or os.path.isfile(pyproject)):
            return None
        # Look for packages/ or src/ subdirectories
        packages: list[PackageInfo] = []
        for sub in ("packages", "src"):
            sub_dir = os.path.join(root, sub)
            if os.path.isdir(sub_dir):
                for entry in sorted(os.listdir(sub_dir)):
                    entry_path = os.path.join(sub_dir, entry)
                    if os.path.isdir(entry_path) and not entry.startswith("."):
                        packages.append(PackageInfo(name=entry, path=entry_path))
        if not packages:
            packages.append(PackageInfo(name=os.path.basename(root), path=root))
        return WorkspaceInfo(workspace_type="pip", packages=packages, root=root)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _read_text(path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def _scan_node_packages(self, root: str) -> list[PackageInfo]:
        """Walk common package directories and find package.json files."""
        packages: list[PackageInfo] = []
        for candidate_dir in ("packages", "apps", "libs", "modules"):
            base = os.path.join(root, candidate_dir)
            if not os.path.isdir(base):
                continue
            for entry in sorted(os.listdir(base)):
                pkg_dir = os.path.join(base, entry)
                pkg_json = os.path.join(pkg_dir, "package.json")
                if os.path.isfile(pkg_json):
                    try:
                        data = json.loads(self._read_text(pkg_json))
                        name = data.get("name", entry)
                        deps = list(data.get("dependencies", {}).keys())
                    except (OSError, json.JSONDecodeError):
                        name = entry
                        deps = []
                    packages.append(PackageInfo(name=name, path=pkg_dir, deps=deps))
        return packages

    def _parse_cargo_workspace(self, root: str, text: str) -> list[PackageInfo]:
        """Extract members from a Cargo.toml [workspace] section."""
        packages: list[PackageInfo] = []
        in_members = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("members"):
                in_members = True
                continue
            if in_members:
                if stripped == "]":
                    break
                cleaned = stripped.strip('",[] ')
                if cleaned:
                    member_path = os.path.join(root, cleaned)
                    packages.append(PackageInfo(name=cleaned, path=member_path))
        return packages

    def _parse_go_work(self, root: str, text: str) -> list[PackageInfo]:
        """Extract use directives from go.work."""
        packages: list[PackageInfo] = []
        in_use = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("use"):
                if "(" in stripped:
                    in_use = True
                    continue
                # single-line use
                mod = stripped.replace("use", "").strip()
                if mod:
                    packages.append(PackageInfo(name=mod, path=os.path.join(root, mod)))
                continue
            if in_use:
                if stripped == ")":
                    break
                if stripped:
                    packages.append(PackageInfo(name=stripped, path=os.path.join(root, stripped)))
        return packages
