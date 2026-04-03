"""License analyzer — compatibility checking and SBOM generation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LicenseInfo:
    """License metadata for a single package."""

    package: str
    license: str
    category: str = "unknown"  # permissive / copyleft / proprietary


# Simple compatibility matrix: project license -> incompatible categories.
_INCOMPATIBLE: dict[str, tuple[str, ...]] = {
    "MIT": ("copyleft", "proprietary"),
    "Apache-2.0": ("copyleft",),
    "BSD-3-Clause": ("copyleft", "proprietary"),
    "GPL-3.0": ("proprietary",),
    "LGPL-3.0": ("proprietary",),
}


class LicenseAnalyzer:
    """Analyse dependency licenses for compatibility and SBOM generation."""

    def __init__(self) -> None:
        self._entries: list[LicenseInfo] = []

    def add(self, info: LicenseInfo) -> None:
        """Register a package's license information."""
        self._entries = [*self._entries, info]

    def check_compatibility(self, project_license: str) -> list[str]:
        """Return names of packages whose category is incompatible with *project_license*."""
        bad_categories = _INCOMPATIBLE.get(project_license, ())
        return [
            e.package
            for e in self._entries
            if e.category in bad_categories
        ]

    def generate_sbom(self) -> dict:
        """Generate a minimal Software Bill of Materials."""
        return {
            "format": "lidco-sbom-1.0",
            "packages": [
                {
                    "name": e.package,
                    "license": e.license,
                    "category": e.category,
                }
                for e in self._entries
            ],
            "total": len(self._entries),
        }

    def list_all(self) -> list[LicenseInfo]:
        """Return every registered :class:`LicenseInfo`."""
        return list(self._entries)

    def summary(self) -> str:
        """Human-readable summary of all licenses."""
        if not self._entries:
            return "No license data."
        lines = [f"{len(self._entries)} package(s):"]
        for e in self._entries:
            lines = [*lines, f"  {e.package}: {e.license} ({e.category})"]
        return "\n".join(lines)
