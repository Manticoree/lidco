"""Dependency checker — Task 848."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class DepStatus:
    """Status of a single dependency."""

    name: str
    installed: bool
    version: Optional[str]
    required_version: Optional[str]
    compatible: bool


def _default_import_check(name: str) -> bool:
    """Return True if *name* can be found via importlib."""
    return importlib.util.find_spec(name) is not None


def _default_version_getter(name: str) -> Optional[str]:
    """Try to get version from importlib.metadata."""
    try:
        from importlib.metadata import version as _ver
        return _ver(name)
    except Exception:  # noqa: BLE001
        return None


def _compare_versions(installed: str, required: str) -> bool:
    """Simple >= comparison of dotted version strings."""
    def _tup(v: str) -> tuple[int, ...]:
        parts: list[int] = []
        for p in v.lstrip(">=<~!").split("."):
            try:
                parts.append(int(p))
            except ValueError:
                break
        return tuple(parts)

    return _tup(installed) >= _tup(required)


class DependencyChecker:
    """Check whether Python packages are installed and version-compatible."""

    def __init__(
        self,
        *,
        _import_check: Callable[[str], bool] | None = None,
        _version_getter: Callable[[str], Optional[str]] | None = None,
    ) -> None:
        self._import_check = _import_check or _default_import_check
        self._version_getter = _version_getter or _default_version_getter
        self._results: list[DepStatus] = []

    def check(self, package_name: str, required_version: str | None = None) -> DepStatus:
        """Check a single package."""
        installed = self._import_check(package_name)
        version: str | None = None
        compatible = True

        if installed:
            version = self._version_getter(package_name)
            if required_version and version:
                compatible = _compare_versions(version, required_version)
            elif required_version and not version:
                compatible = True  # can't verify, assume ok

        result = DepStatus(
            name=package_name,
            installed=installed,
            version=version,
            required_version=required_version,
            compatible=compatible if installed else False,
        )
        self._results.append(result)
        return result

    def check_all(self, packages: list[str | tuple[str, str]]) -> list[DepStatus]:
        """Check multiple packages. Items can be 'name' or ('name', 'version')."""
        results: list[DepStatus] = []
        for pkg in packages:
            if isinstance(pkg, tuple):
                name, ver = pkg
                results.append(self.check(name, ver))
            else:
                results.append(self.check(pkg))
        return results

    def missing(self) -> list[str]:
        """Names of packages not installed from the last check_all."""
        return [r.name for r in self._results if not r.installed]

    def summary(self) -> str:
        """Formatted summary of checked dependencies."""
        results = self._results
        if not results:
            return "No dependencies checked."
        installed = sum(1 for r in results if r.installed)
        compat = sum(1 for r in results if r.compatible)
        lines = [f"Dependencies: {installed}/{len(results)} installed, {compat} compatible"]
        for r in results:
            status = "ok" if r.installed and r.compatible else "MISSING" if not r.installed else "INCOMPAT"
            ver = r.version or "?"
            lines.append(f"  [{status}] {r.name} {ver}" + (f" (need {r.required_version})" if r.required_version else ""))
        return "\n".join(lines)
