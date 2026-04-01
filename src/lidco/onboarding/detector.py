"""Project type and framework detection — task 1102."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum


class ProjectType(Enum):
    """Known project types."""

    PYTHON = "python"
    NODE = "node"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    RUBY = "ruby"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FrameworkInfo:
    """Detected framework metadata."""

    name: str
    version: str | None
    config_file: str


@dataclass(frozen=True)
class ProjectInfo:
    """Full project detection result."""

    project_type: ProjectType
    frameworks: tuple[FrameworkInfo, ...]
    build_system: str | None
    is_monorepo: bool
    root_path: str


# Marker files for each project type
_TYPE_MARKERS: tuple[tuple[str, ProjectType], ...] = (
    ("pyproject.toml", ProjectType.PYTHON),
    ("setup.py", ProjectType.PYTHON),
    ("setup.cfg", ProjectType.PYTHON),
    ("requirements.txt", ProjectType.PYTHON),
    ("package.json", ProjectType.NODE),
    ("Cargo.toml", ProjectType.RUST),
    ("go.mod", ProjectType.GO),
    ("pom.xml", ProjectType.JAVA),
    ("build.gradle", ProjectType.JAVA),
    ("Gemfile", ProjectType.RUBY),
)

# Framework detection rules: (config_file, framework_name, project_type)
_FRAMEWORK_RULES: tuple[tuple[str, str, ProjectType], ...] = (
    ("django/conf/__init__.py", "django", ProjectType.PYTHON),
    ("manage.py", "django", ProjectType.PYTHON),
    ("flask", "flask", ProjectType.PYTHON),
    ("fastapi", "fastapi", ProjectType.PYTHON),
    ("next.config.js", "nextjs", ProjectType.NODE),
    ("next.config.mjs", "nextjs", ProjectType.NODE),
    ("nuxt.config.ts", "nuxt", ProjectType.NODE),
    ("angular.json", "angular", ProjectType.NODE),
    ("vite.config.ts", "vite", ProjectType.NODE),
    ("vite.config.js", "vite", ProjectType.NODE),
    ("tsconfig.json", "typescript", ProjectType.NODE),
    ("Rakefile", "rake", ProjectType.RUBY),
    ("rails", "rails", ProjectType.RUBY),
)

# Build system markers
_BUILD_SYSTEMS: tuple[tuple[str, str], ...] = (
    ("Makefile", "make"),
    ("CMakeLists.txt", "cmake"),
    ("build.gradle", "gradle"),
    ("pom.xml", "maven"),
    ("Cargo.toml", "cargo"),
    ("pyproject.toml", "pyproject"),
    ("setup.py", "setuptools"),
)


class ProjectDetector:
    """Detect project type, frameworks, and build system from a directory."""

    def detect(self, path: str) -> ProjectInfo:
        """Run full detection and return a *ProjectInfo*."""
        path = os.path.abspath(path)
        return ProjectInfo(
            project_type=self.detect_type(path),
            frameworks=self.detect_frameworks(path),
            build_system=self._detect_build_system(path),
            is_monorepo=self.is_monorepo(path),
            root_path=path,
        )

    def detect_type(self, path: str) -> ProjectType:
        """Return the best-guess *ProjectType* for *path*."""
        path = os.path.abspath(path)
        for marker, ptype in _TYPE_MARKERS:
            if os.path.exists(os.path.join(path, marker)):
                return ptype
        return ProjectType.UNKNOWN

    def detect_frameworks(self, path: str) -> tuple[FrameworkInfo, ...]:
        """Return detected frameworks for *path*."""
        path = os.path.abspath(path)
        found: list[FrameworkInfo] = []
        seen: set[str] = set()

        # File-based detection
        for config_file, fw_name, _ptype in _FRAMEWORK_RULES:
            if fw_name in seen:
                continue
            full = os.path.join(path, config_file)
            if os.path.exists(full):
                seen.add(fw_name)
                found.append(FrameworkInfo(name=fw_name, version=None, config_file=config_file))

        # package.json dependency detection
        pkg_json = os.path.join(path, "package.json")
        if os.path.isfile(pkg_json):
            found.extend(self._frameworks_from_package_json(pkg_json, seen))

        # requirements.txt dependency detection
        req_txt = os.path.join(path, "requirements.txt")
        if os.path.isfile(req_txt):
            found.extend(self._frameworks_from_requirements(req_txt, seen))

        return tuple(found)

    def is_monorepo(self, path: str) -> bool:
        """Heuristic: return *True* if *path* looks like a monorepo."""
        path = os.path.abspath(path)
        # Workspace config files
        monorepo_markers = (
            "lerna.json",
            "nx.json",
            "turbo.json",
            "pnpm-workspace.yaml",
        )
        for marker in monorepo_markers:
            if os.path.exists(os.path.join(path, marker)):
                return True

        # package.json with workspaces field
        pkg_json = os.path.join(path, "package.json")
        if os.path.isfile(pkg_json):
            try:
                with open(pkg_json, encoding="utf-8") as fh:
                    data = json.load(fh)
                if "workspaces" in data:
                    return True
            except (json.JSONDecodeError, OSError):
                pass

        # Cargo workspace
        cargo_toml = os.path.join(path, "Cargo.toml")
        if os.path.isfile(cargo_toml):
            try:
                with open(cargo_toml, encoding="utf-8") as fh:
                    content = fh.read()
                if "[workspace]" in content:
                    return True
            except OSError:
                pass

        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_build_system(self, path: str) -> str | None:
        for marker, name in _BUILD_SYSTEMS:
            if os.path.exists(os.path.join(path, marker)):
                return name
        return None

    def _frameworks_from_package_json(
        self, pkg_path: str, seen: set[str]
    ) -> list[FrameworkInfo]:
        results: list[FrameworkInfo] = []
        try:
            with open(pkg_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return results

        deps: dict[str, str] = {}
        deps.update(data.get("dependencies", {}))
        deps.update(data.get("devDependencies", {}))

        known = {"react", "vue", "svelte", "express", "next", "angular"}
        for dep_name, version in deps.items():
            base = dep_name.split("/")[-1]
            if base in known and base not in seen:
                seen.add(base)
                results.append(
                    FrameworkInfo(name=base, version=version, config_file="package.json")
                )
        return results

    def _frameworks_from_requirements(
        self, req_path: str, seen: set[str]
    ) -> list[FrameworkInfo]:
        results: list[FrameworkInfo] = []
        known = {"django", "flask", "fastapi", "celery", "pytest"}
        try:
            with open(req_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # e.g. "django==4.2" or "flask>=2.0"
                    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
                        if sep in line:
                            name, version = line.split(sep, 1)
                            name = name.strip().lower()
                            if name in known and name not in seen:
                                seen.add(name)
                                results.append(
                                    FrameworkInfo(
                                        name=name,
                                        version=version.strip(),
                                        config_file="requirements.txt",
                                    )
                                )
                            break
                    else:
                        name = line.strip().lower()
                        if name in known and name not in seen:
                            seen.add(name)
                            results.append(
                                FrameworkInfo(
                                    name=name,
                                    version=None,
                                    config_file="requirements.txt",
                                )
                            )
        except OSError:
            pass
        return results
