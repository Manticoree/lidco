"""Dependency gap detector — compares declared vs installed packages.

Supports:
- PEP 621 ``[project.dependencies]`` and ``[project.optional-dependencies]``
- Poetry ``[tool.poetry.dependencies]``
- ``requirements.txt`` files

Usage::

    from lidco.tools.dep_checker import check_dependencies, _parse_pyproject_deps

    deps = _parse_pyproject_deps(Path("pyproject.toml"))
    issues = check_dependencies(deps)
    print(format_issues(issues, declared_count=len(deps)))
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DepIssue:
    """A single dependency problem found during the check.

    Attributes:
        kind:      ``"MISSING"`` — package not installed at all;
                   ``"MISMATCH"`` — installed version fails the specifier.
        package:   Canonical package name from the requirement specifier.
        required:  Version specifier string (e.g. ``">=2.0"``), or ``"any"``.
        installed: Installed version string, or ``""`` when not installed.
        detail:    Human-readable explanation / suggested fix.
    """

    kind: str
    package: str
    required: str
    installed: str
    detail: str


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_pyproject_deps(path: Path) -> list[str]:
    """Extract raw dependency specifier strings from *pyproject.toml*.

    Handles both PEP 621 (``[project.dependencies]``) and Poetry
    (``[tool.poetry.dependencies]``) layouts.  Returns an empty list when the
    file is absent or contains invalid TOML.
    """
    try:
        with open(path, "rb") as fh:
            data: dict[str, Any] = tomllib.load(fh)
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError, Exception):
        return []

    deps: list[str] = []

    # PEP 621 ----------------------------------------------------------------
    project = data.get("project", {})
    if isinstance(project, dict):
        for req in project.get("dependencies", []):
            if isinstance(req, str):
                deps.append(req)
        # Optional / extras
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for extra_list in optional.values():
                for req in (extra_list or []):
                    if isinstance(req, str):
                        deps.append(req)

    # Poetry ------------------------------------------------------------------
    poetry_deps = (
        data.get("tool", {})
        .get("poetry", {})
        .get("dependencies", {})
    )
    if isinstance(poetry_deps, dict):
        for pkg, spec in poetry_deps.items():
            if pkg.lower() == "python":
                continue
            if isinstance(spec, str):
                if spec == "*":
                    deps.append(pkg)
                else:
                    deps.append(f"{pkg}{spec}")
            elif isinstance(spec, dict):
                ver = spec.get("version", "")
                if ver and ver != "*":
                    deps.append(f"{pkg}{ver}")
                else:
                    deps.append(pkg)

    return deps


def _parse_requirements_txt(path: Path) -> list[str]:
    """Parse *requirements.txt* and return raw requirement specifier strings.

    Lines that are blank, start with ``#``, or start with ``-`` (flags like
    ``-r``, ``--index-url``) are ignored.  Inline ``#`` comments are stripped.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    result: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip inline comments
        if "#" in line:
            line = line[: line.index("#")].strip()
        if line:
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------------------------


def _normalize_pkg(name: str) -> str:
    """Lowercase and replace hyphens/underscores for case-insensitive matching.

    PEP 503 normalisation: lowercase + replace ``[-_.]`` with ``-``.  We
    use a simpler version (just lowercase + replace ``-`` and ``_``) which
    covers the vast majority of real packages.
    """
    return name.lower().replace("-", "_").replace(".", "_")


# ---------------------------------------------------------------------------
# Core checker
# ---------------------------------------------------------------------------


def check_dependencies(
    declared: list[str],
    installed: dict[str, str] | None = None,
) -> list[DepIssue]:
    """Check declared dependency specifiers against installed packages.

    Args:
        declared:  List of requirement specifier strings, e.g.
                   ``["pydantic>=2.0", "litellm"]``.
        installed: Mapping of ``package_name → version``.  Pass a dict for
                   deterministic testing.  When ``None``, the real installed
                   environment is queried via :mod:`importlib.metadata`.

    Returns:
        A (possibly empty) list of :class:`DepIssue` objects.
    """
    # Build a normalised lookup from the caller-supplied dict.
    norm_installed: dict[str, str] | None = None
    if installed is not None:
        norm_installed = {_normalize_pkg(k): v for k, v in installed.items()}

    issues: list[DepIssue] = []

    for req_str in declared:
        req_str = req_str.strip()
        if not req_str:
            continue

        try:
            req = Requirement(req_str)
        except (InvalidRequirement, Exception):
            continue

        pkg_name = req.name

        # Resolve installed version -------------------------------------------
        inst_ver: str | None = None
        if norm_installed is not None:
            inst_ver = norm_installed.get(_normalize_pkg(pkg_name))
        else:
            try:
                inst_ver = _pkg_version(pkg_name)
            except PackageNotFoundError:
                inst_ver = None

        # Check presence -------------------------------------------------------
        if inst_ver is None:
            spec_str = str(req.specifier) or "any"
            issues.append(
                DepIssue(
                    kind="MISSING",
                    package=pkg_name,
                    required=spec_str,
                    installed="",
                    detail=f'Not installed. Run: pip install "{pkg_name}"',
                )
            )
            continue

        # Check version specifier ----------------------------------------------
        if req.specifier:
            try:
                if not req.specifier.contains(inst_ver, prereleases=True):
                    issues.append(
                        DepIssue(
                            kind="MISMATCH",
                            package=pkg_name,
                            required=str(req.specifier),
                            installed=inst_ver,
                            detail=(
                                f"Installed {inst_ver} does not satisfy"
                                f" {req.specifier}"
                            ),
                        )
                    )
            except Exception:
                pass  # unparseable version string — skip silently

    return issues


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_issues(issues: list[DepIssue], declared_count: int) -> str:
    """Format a list of :class:`DepIssue` objects as a Markdown string.

    Returns an ``[OK]`` line when *issues* is empty.
    """
    if not issues:
        return f"[OK] All {declared_count} declared dependencies are satisfied."

    missing = [i for i in issues if i.kind == "MISSING"]
    mismatch = [i for i in issues if i.kind == "MISMATCH"]

    lines: list[str] = [
        f"Dependency Check: {len(issues)} issue(s) in {declared_count} declared packages",
    ]

    if missing:
        lines.append(f"\nMissing ({len(missing)}):")
        for iss in missing:
            spec = f" {iss.required}" if iss.required != "any" else ""
            lines.append(f"  {iss.package}{spec}")
            lines.append(f"    {iss.detail}")

    if mismatch:
        lines.append(f"\nVersion mismatch ({len(mismatch)}):")
        for iss in mismatch:
            lines.append(
                f"  {iss.package}: requires {iss.required},"
                f" installed {iss.installed}"
            )
            lines.append(f"    {iss.detail}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class DependencyCheckerTool(BaseTool):
    """Check declared vs installed Python dependencies.

    Reads ``pyproject.toml`` and/or ``requirements.txt`` from the given
    directory and compares each declared requirement against the currently
    installed environment.  Reports missing packages and version mismatches.
    """

    @property
    def name(self) -> str:
        return "check_dependencies"

    @property
    def description(self) -> str:
        return (
            "Check declared Python dependencies (pyproject.toml / requirements.txt) "
            "against the installed environment. Reports missing packages and version "
            "mismatches."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description=(
                    "Project directory to scan. Defaults to current working directory."
                ),
                required=False,
                default=".",
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        path_str: str = kwargs.get("path", ".")
        root = Path(path_str).resolve()

        if not root.exists():
            return ToolResult(
                output=f"Path not found: {path_str}",
                success=False,
                error=f"Path not found: {path_str}",
            )
        if not root.is_dir():
            root = root.parent

        # Collect declared dependencies from all supported manifest files.
        declared: list[str] = []
        sources_found: list[str] = []

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            parsed = _parse_pyproject_deps(pyproject)
            if parsed:
                declared.extend(parsed)
                sources_found.append("pyproject.toml")

        requirements = root / "requirements.txt"
        if requirements.exists():
            parsed = _parse_requirements_txt(requirements)
            if parsed:
                declared.extend(parsed)
                sources_found.append("requirements.txt")

        if not declared:
            return ToolResult(
                output=(
                    "No dependency declarations found. "
                    "Expected pyproject.toml or requirements.txt."
                ),
                success=True,
                metadata={"declared": 0, "issues": 0},
            )

        # Check against live environment (installed=None → importlib.metadata).
        issues = check_dependencies(declared, installed=None)
        output = format_issues(issues, declared_count=len(declared))

        if sources_found:
            header = f"Sources: {', '.join(sources_found)} ({len(declared)} packages)\n\n"
            output = header + output

        return ToolResult(
            output=output,
            success=(len(issues) == 0),
            metadata={
                "declared": len(declared),
                "issues": len(issues),
                "missing": sum(1 for i in issues if i.kind == "MISSING"),
                "mismatch": sum(1 for i in issues if i.kind == "MISMATCH"),
                "sources": sources_found,
            },
        )
