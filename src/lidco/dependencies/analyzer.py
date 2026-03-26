"""
Dependency Analyzer — Dependabot/Snyk-style dependency intelligence.

Supports:
  - requirements.txt / requirements*.txt
  - pyproject.toml (dependencies + dev-dependencies)
  - package.json (dependencies + devDependencies)

Detects:
  - Pinned vs unpinned packages
  - Packages imported in code but missing from manifest (undeclared)
  - Packages in manifest but never imported (unused)
  - Known insecure version ranges (simple built-in database)

No network calls — all analysis is local / static.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PackageInfo:
    name: str
    version_spec: str   # e.g. ">=1.2,<2.0" or "1.2.3" or ""
    source: str         # "requirements.txt", "pyproject.toml", "package.json"
    is_dev: bool = False
    is_pinned: bool = False  # exact version ==x.y.z


@dataclass
class DependencyIssue:
    severity: str       # "high" | "medium" | "low" | "info"
    package: str
    issue_type: str     # "unpinned" | "unused" | "undeclared" | "known_vulnerable"
    description: str


@dataclass
class DependencyReport:
    packages: list[PackageInfo]
    issues: list[DependencyIssue]
    import_names: list[str]     # top-level names imported in source files
    manifest_names: list[str]   # package names from manifest

    @property
    def high_issues(self) -> list[DependencyIssue]:
        return [i for i in self.issues if i.severity == "high"]

    @property
    def medium_issues(self) -> list[DependencyIssue]:
        return [i for i in self.issues if i.severity == "medium"]

    def summary(self) -> str:
        total = len(self.packages)
        highs = len(self.high_issues)
        meds = len(self.medium_issues)
        return (
            f"{total} packages | "
            f"{highs} high | {meds} medium | "
            f"{len(self.issues) - highs - meds} low/info issues"
        )


# ---------------------------------------------------------------------------
# Minimal built-in vulnerability database (package → unsafe version patterns)
# ---------------------------------------------------------------------------

_KNOWN_VULNERABLE: dict[str, list[tuple[str, str]]] = {
    # (spec_pattern_regex, description)
    "pillow": [
        (r"^[<>]?=?\s*[0-5]\.", "Pillow < 6.0 has multiple CVEs (buffer overflows)"),
        (r"^==\s*9\.0\.0", "Pillow 9.0.0 has CVE-2023-44271"),
    ],
    "cryptography": [
        (r"^[<>]?=?\s*[0-2]\.", "cryptography < 3.0 has weak cipher support"),
    ],
    "requests": [
        (r"^[<>]?=?\s*2\.[0-9]\.", "requests < 2.10 lacks certificate pinning"),
    ],
    "urllib3": [
        (r"^[<>]?=?\s*1\.[0-9]\.", "urllib3 < 1.25 SSL verification issues"),
    ],
    "django": [
        (r"^[<>]?=?\s*[12]\.", "Django 1.x/2.x are end-of-life"),
    ],
    "flask": [
        (r"^[<>]?=?\s*0\.", "Flask < 1.0 has security vulnerabilities"),
    ],
    "pyyaml": [
        (r"^[<>]?=?\s*[0-4]\.", "PyYAML < 5.1 allows arbitrary code execution via yaml.load"),
    ],
    "jinja2": [
        (r"^[<>]?=?\s*2\.[0-9]\.", "Jinja2 2.x has sandbox escape CVEs"),
    ],
}


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_requirements_txt(path: Path) -> list[PackageInfo]:
    """Parse a requirements.txt file."""
    packages = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip inline comments
        line = line.split("#")[0].strip()
        # Match "name[extras]specifier"
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[.*?\])?\s*([><=!~^,\s\d.*]+)?$", line)
        if m:
            name = m.group(1).strip()
            spec = (m.group(3) or "").strip()
            is_pinned = bool(re.match(r"^==\s*[\d.]+$", spec))
            packages.append(PackageInfo(
                name=name.lower(),
                version_spec=spec,
                source=path.name,
                is_pinned=is_pinned,
            ))
    return packages


def _parse_pyproject_toml(path: Path) -> list[PackageInfo]:
    """Parse pyproject.toml using simple regex (no toml library required)."""
    packages = []
    text = path.read_text(encoding="utf-8", errors="ignore")

    # Find [project.dependencies] and [project.optional-dependencies.*] blocks
    # and [tool.poetry.dependencies] / [tool.poetry.dev-dependencies]
    sections = {
        r"\[project\.dependencies\]": False,
        r"\[tool\.poetry\.dependencies\]": False,
        r"\[tool\.poetry\.dev-dependencies\]": True,
        r"\[project\.optional-dependencies\.\w+\]": True,
    }

    for section_pattern, is_dev in sections.items():
        # Find the section and collect lines until next [section]
        m = re.search(section_pattern, text, re.IGNORECASE)
        if not m:
            continue
        start = m.end()
        end_m = re.search(r"\n\[", text[start:])
        block = text[start: start + (end_m.start() if end_m else len(text))]

        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            # Format: "name = '^1.2'" or just "name>=1.2"
            m2 = re.match(r'^"?([A-Za-z0-9_.\-]+)"?\s*[=:]\s*"?([^",\n]*)"?', line)
            if m2:
                name = m2.group(1).strip().lower()
                spec = m2.group(2).strip().strip('"\'')
                if name in ("python", "python-requires"):
                    continue
                is_pinned = bool(re.match(r"^==\s*[\d.]+$", spec))
                packages.append(PackageInfo(
                    name=name,
                    version_spec=spec,
                    source="pyproject.toml",
                    is_dev=is_dev,
                    is_pinned=is_pinned,
                ))

    return packages


def _parse_package_json(path: Path) -> list[PackageInfo]:
    """Parse package.json dependencies."""
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    packages = []
    for key, is_dev in (("dependencies", False), ("devDependencies", True)):
        deps = data.get(key, {})
        if not isinstance(deps, dict):
            continue
        for name, spec in deps.items():
            spec = str(spec)
            is_pinned = bool(re.match(r"^\d+\.\d+\.\d+$", spec))
            packages.append(PackageInfo(
                name=name.lower(),
                version_spec=spec,
                source="package.json",
                is_dev=is_dev,
                is_pinned=is_pinned,
            ))
    return packages


# ---------------------------------------------------------------------------
# Import collector
# ---------------------------------------------------------------------------

def _collect_imports(root: Path, extensions: tuple[str, ...] = (".py",)) -> set[str]:
    """Collect top-level package names imported across all source files."""
    names: set[str] = set()
    for path in root.rglob("*"):
        if path.suffix not in extensions:
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), str(path))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".")[0].lower())
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0].lower())
    return names


# ---------------------------------------------------------------------------
# DependencyAnalyzer
# ---------------------------------------------------------------------------

# Packages that are always safe to mark as "used" (build tools, etc.)
_ALWAYS_USED = frozenset({
    "setuptools", "wheel", "pip", "build", "twine",
    "pytest", "pytest-cov", "coverage", "tox",
    "mypy", "ruff", "flake8", "pylint", "black", "isort",
    "pre-commit", "nox", "hatch", "flit",
    "types-requests", "types-pyyaml",
})

# Common package name → import name mappings
_CANONICAL: dict[str, str] = {
    "pillow": "pil",
    "beautifulsoup4": "bs4",
    "scikit-learn": "sklearn",
    "python-dateutil": "dateutil",
    "pyyaml": "yaml",
    "pyzmq": "zmq",
    "opencv-python": "cv2",
    "python-dotenv": "dotenv",
    "typing-extensions": "typing_extensions",
    "sqlalchemy": "sqlalchemy",
    "attrs": "attr",
}


class DependencyAnalyzer:
    """
    Analyze project dependencies for issues.

    Parameters
    ----------
    project_root : str | None
        Project root directory. Defaults to cwd.
    check_unused : bool
        Whether to check for unused dependencies (requires AST scan).
    check_unpinned : bool
        Whether to flag unpinned version specs.
    """

    def __init__(
        self,
        project_root: str | None = None,
        check_unused: bool = True,
        check_unpinned: bool = True,
        check_vulnerable: bool = True,
    ) -> None:
        self._root = Path(project_root) if project_root else Path.cwd()
        self._check_unused = check_unused
        self._check_unpinned = check_unpinned
        self._check_vulnerable = check_vulnerable

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self) -> DependencyReport:
        packages = self._load_packages()
        import_names = (
            _collect_imports(self._root) if self._check_unused else set()
        )
        manifest_names = {p.name for p in packages}
        issues: list[DependencyIssue] = []

        for pkg in packages:
            if self._check_unpinned and not pkg.is_pinned and not pkg.is_dev:
                issues.append(DependencyIssue(
                    severity="low",
                    package=pkg.name,
                    issue_type="unpinned",
                    description=(
                        f"'{pkg.name}' is not pinned to an exact version "
                        f"(spec: '{pkg.version_spec or 'any'}')."
                    ),
                ))

            if self._check_vulnerable:
                for vuln_pkg, patterns in _KNOWN_VULNERABLE.items():
                    if pkg.name != vuln_pkg:
                        continue
                    for pattern, desc in patterns:
                        if re.search(pattern, pkg.version_spec):
                            issues.append(DependencyIssue(
                                severity="high",
                                package=pkg.name,
                                issue_type="known_vulnerable",
                                description=desc,
                            ))

        if self._check_unused and import_names:
            for pkg in packages:
                if pkg.name in _ALWAYS_USED or pkg.is_dev:
                    continue
                import_alias = _CANONICAL.get(pkg.name, pkg.name.replace("-", "_"))
                if (
                    pkg.name not in import_names
                    and import_alias not in import_names
                ):
                    issues.append(DependencyIssue(
                        severity="info",
                        package=pkg.name,
                        issue_type="unused",
                        description=(
                            f"'{pkg.name}' appears in manifest but is never imported."
                        ),
                    ))

            # Undeclared: imported but not in manifest
            stdlib = _get_stdlib_modules()
            for name in sorted(import_names):
                if name in manifest_names:
                    continue
                # Check canonical reverse mapping
                canonical_pkg = next(
                    (k for k, v in _CANONICAL.items() if v == name), None
                )
                if canonical_pkg and canonical_pkg in manifest_names:
                    continue
                if name in stdlib or name in _ALWAYS_USED:
                    continue
                if name.startswith("_"):
                    continue
                issues.append(DependencyIssue(
                    severity="medium",
                    package=name,
                    issue_type="undeclared",
                    description=(
                        f"'{name}' is imported in code but not found in any manifest."
                    ),
                ))

        return DependencyReport(
            packages=packages,
            issues=issues,
            import_names=sorted(import_names),
            manifest_names=sorted(manifest_names),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_packages(self) -> list[PackageInfo]:
        packages: list[PackageInfo] = []
        seen: set[str] = set()

        # requirements*.txt
        for req_file in sorted(self._root.glob("requirements*.txt")):
            for pkg in _parse_requirements_txt(req_file):
                if pkg.name not in seen:
                    seen.add(pkg.name)
                    packages.append(pkg)

        # pyproject.toml
        pyproject = self._root / "pyproject.toml"
        if pyproject.exists():
            for pkg in _parse_pyproject_toml(pyproject):
                if pkg.name not in seen:
                    seen.add(pkg.name)
                    packages.append(pkg)

        # package.json
        package_json = self._root / "package.json"
        if package_json.exists():
            for pkg in _parse_package_json(package_json):
                if pkg.name not in seen:
                    seen.add(pkg.name)
                    packages.append(pkg)

        return packages


# ---------------------------------------------------------------------------
# stdlib module list (Python 3.11+)
# ---------------------------------------------------------------------------

def _get_stdlib_modules() -> frozenset[str]:
    """Return a frozenset of stdlib top-level module names."""
    try:
        import sys
        return frozenset(sys.stdlib_module_names)  # type: ignore[attr-defined]
    except AttributeError:
        # Fallback for older Python
        return frozenset({
            "abc", "ast", "asyncio", "builtins", "collections", "contextlib",
            "copy", "dataclasses", "datetime", "enum", "functools", "gc",
            "hashlib", "heapq", "inspect", "io", "itertools", "json", "logging",
            "math", "os", "pathlib", "pickle", "platform", "pprint", "queue",
            "random", "re", "shlex", "shutil", "signal", "socket", "sqlite3",
            "string", "struct", "subprocess", "sys", "tempfile", "textwrap",
            "threading", "time", "traceback", "types", "typing", "unittest",
            "urllib", "uuid", "warnings", "weakref", "xml", "zipfile",
            "concurrent", "http", "importlib", "multiprocessing",
            "configparser", "csv", "decimal", "difflib", "email", "ftplib",
            "glob", "gzip", "hmac", "html", "http", "imaplib", "ipaddress",
            "keyword", "linecache", "locale", "mimetypes", "numbers",
            "operator", "optparse", "pdb", "pkgutil", "pstats", "pty",
            "readline", "runpy", "secrets", "select", "shelve", "smtplib",
            "sndhdr", "socketserver", "ssl", "stat", "statistics", "tarfile",
            "telnetlib", "termios", "test", "tkinter", "token", "tokenize",
            "tomllib", "trace", "tty", "turtle", "uu", "venv", "wave",
            "wsgiref", "xdrlib", "xmlrpc", "zipimport", "zlib", "zoneinfo",
        })
