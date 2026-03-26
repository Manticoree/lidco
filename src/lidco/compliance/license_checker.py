"""
License Checker — FOSSA/license-checker-style OSS compliance analysis.

Reads package metadata (METADATA, PKG-INFO, dist-info) from the active
Python environment to determine the license of each installed package.

Also parses requirements*.txt / package.json to list declared dependencies.

Classification:
  permissive  — MIT, BSD, Apache, ISC, Unlicense, Zlib, PSF, WTFPL
  weak_copyleft — LGPL, MPL, EPL, CDDL
  copyleft    — GPL, AGPL
  unknown     — cannot determine

Incompatibility rules (configurable):
  By default, "copyleft" licenses are flagged if your project_license is
  "MIT" or "Apache-2.0" (i.e. you can't redistribute GPL code in a
  proprietary/permissive project without compliance work).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# License classification
# ---------------------------------------------------------------------------

_PERMISSIVE = frozenset({
    "mit", "bsd", "bsd-2-clause", "bsd-3-clause", "apache", "apache-2.0",
    "apache 2.0", "isc", "unlicense", "the unlicense", "zlib", "psf",
    "python software foundation license", "wtfpl", "cc0", "cc0-1.0",
    "0bsd", "artistic-2.0", "eupl-1.1", "eupl-1.2",
})

_WEAK_COPYLEFT = frozenset({
    "lgpl", "lgpl-2.0", "lgpl-2.1", "lgpl-3.0",
    "mpl", "mpl-2.0", "mozilla public license 2.0",
    "epl", "epl-1.0", "epl-2.0", "eclipse public license",
    "cddl", "cddl-1.0",
    "eupl", "cecill-c",
})

_COPYLEFT = frozenset({
    "gpl", "gpl-2.0", "gpl-3.0", "gnu general public license",
    "agpl", "agpl-3.0", "gnu affero general public license",
    "osl-3.0", "open software license",
    "cecill-2.1",
})


def _classify(license_str: str) -> str:
    """Return 'permissive' | 'weak_copyleft' | 'copyleft' | 'unknown'."""
    if not license_str or license_str.lower() in ("unknown", "none", ""):
        return "unknown"
    low = license_str.lower().strip()
    # Check weak_copyleft BEFORE copyleft so "lgpl" isn't caught by "gpl"
    for name in _WEAK_COPYLEFT:
        if name in low:
            return "weak_copyleft"
    for name in _COPYLEFT:
        if name in low:
            return "copyleft"
    for name in _PERMISSIVE:
        if name in low:
            return "permissive"
    return "unknown"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PackageLicense:
    name: str
    version: str
    license: str          # raw license string from metadata
    classification: str   # permissive | weak_copyleft | copyleft | unknown
    homepage: str = ""
    source: str = ""      # "dist-info" | "requirements" | "package.json"


@dataclass
class LicenseIssue:
    severity: str         # "error" | "warning" | "info"
    package: str
    license: str
    classification: str
    description: str


@dataclass
class LicenseReport:
    packages: list[PackageLicense]
    issues: list[LicenseIssue]
    project_license: str

    @property
    def by_classification(self) -> dict[str, list[PackageLicense]]:
        result: dict[str, list[PackageLicense]] = {}
        for pkg in self.packages:
            result.setdefault(pkg.classification, []).append(pkg)
        return result

    def summary(self) -> str:
        by_class = self.by_classification
        parts = [f"{len(self.packages)} packages"]
        for cls in ("permissive", "weak_copyleft", "copyleft", "unknown"):
            count = len(by_class.get(cls, []))
            if count:
                parts.append(f"{count} {cls.replace('_', '-')}")
        if self.issues:
            parts.append(f"{len(self.issues)} issues")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# Metadata readers
# ---------------------------------------------------------------------------

def _read_dist_info(site_packages: Path) -> list[PackageLicense]:
    """Read installed package metadata from site-packages dist-info dirs."""
    packages = []
    for dist_dir in site_packages.glob("*.dist-info"):
        metadata_file = dist_dir / "METADATA"
        if not metadata_file.exists():
            metadata_file = dist_dir / "PKG-INFO"
        if not metadata_file.exists():
            continue

        meta = _parse_metadata(metadata_file)
        name = meta.get("Name", dist_dir.name.split("-")[0])
        version = meta.get("Version", "")
        license_str = meta.get("License", "") or meta.get("License-Expression", "")
        # Fallback: check Classifier: License :: ...
        classifiers = meta.get("_classifiers", [])
        if not license_str:
            for clf in classifiers:
                if clf.startswith("License ::"):
                    parts = clf.split(" :: ")
                    if len(parts) >= 3:
                        license_str = parts[-1].strip()
                        break

        packages.append(PackageLicense(
            name=name.lower(),
            version=version,
            license=license_str or "unknown",
            classification=_classify(license_str),
            homepage=meta.get("Home-page", ""),
            source="dist-info",
        ))
    return packages


def _parse_metadata(path: Path) -> dict[str, str]:
    """Parse RFC-822-style metadata file."""
    meta: dict[str, str] = {}
    classifiers: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ": " in line:
            key, _, value = line.partition(": ")
            key = key.strip()
            value = value.strip()
            if key == "Classifier":
                classifiers.append(value)
            else:
                meta.setdefault(key, value)
    meta["_classifiers"] = classifiers  # type: ignore[assignment]
    return meta


def _read_package_json(path: Path) -> list[PackageLicense]:
    """Extract license info from package.json (Node.js deps)."""
    import json
    packages = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    # Top-level project info
    lic = data.get("license", "unknown")
    if isinstance(lic, dict):
        lic = lic.get("type", "unknown")
    packages.append(PackageLicense(
        name=data.get("name", "project").lower(),
        version=data.get("version", ""),
        license=str(lic),
        classification=_classify(str(lic)),
        source="package.json",
    ))
    return packages


# ---------------------------------------------------------------------------
# LicenseChecker
# ---------------------------------------------------------------------------

class LicenseChecker:
    """
    Check licenses of all installed/declared dependencies.

    Parameters
    ----------
    project_root : str | None
        Root of the project (for package.json lookup).
    project_license : str
        Your project's license (e.g. "MIT"). Used to detect incompatibilities.
    flag_copyleft : bool
        Raise issues for GPL/AGPL dependencies in permissive projects.
    flag_unknown : bool
        Warn about packages with unknown/undetectable licenses.
    site_packages_path : str | None
        Override the site-packages directory. Auto-detected if None.
    """

    def __init__(
        self,
        project_root: str | None = None,
        project_license: str = "MIT",
        flag_copyleft: bool = True,
        flag_unknown: bool = True,
        site_packages_path: str | None = None,
    ) -> None:
        self._root = Path(project_root) if project_root else Path.cwd()
        self._project_license = project_license
        self._flag_copyleft = flag_copyleft
        self._flag_unknown = flag_unknown
        self._site_packages = (
            Path(site_packages_path)
            if site_packages_path
            else self._detect_site_packages()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self) -> LicenseReport:
        packages = self._collect_packages()
        issues = self._detect_issues(packages)
        return LicenseReport(
            packages=packages,
            issues=issues,
            project_license=self._project_license,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_packages(self) -> list[PackageLicense]:
        packages: dict[str, PackageLicense] = {}

        # Installed packages from dist-info
        if self._site_packages and self._site_packages.is_dir():
            for pkg in _read_dist_info(self._site_packages):
                packages[pkg.name] = pkg

        # package.json
        pkg_json = self._root / "package.json"
        if pkg_json.exists():
            for pkg in _read_package_json(pkg_json):
                if pkg.name not in packages:
                    packages[pkg.name] = pkg

        return list(packages.values())

    def _detect_issues(self, packages: list[PackageLicense]) -> list[LicenseIssue]:
        issues: list[LicenseIssue] = []
        my_class = _classify(self._project_license)

        for pkg in packages:
            if self._flag_copyleft and pkg.classification == "copyleft":
                if my_class == "permissive":
                    issues.append(LicenseIssue(
                        severity="error",
                        package=pkg.name,
                        license=pkg.license,
                        classification=pkg.classification,
                        description=(
                            f"'{pkg.name}' uses {pkg.license} (copyleft). "
                            f"May be incompatible with your {self._project_license} project."
                        ),
                    ))

            elif pkg.classification == "weak_copyleft":
                issues.append(LicenseIssue(
                    severity="warning",
                    package=pkg.name,
                    license=pkg.license,
                    classification=pkg.classification,
                    description=(
                        f"'{pkg.name}' uses {pkg.license} (weak copyleft). "
                        f"Review distribution requirements."
                    ),
                ))

            if self._flag_unknown and pkg.classification == "unknown":
                issues.append(LicenseIssue(
                    severity="warning",
                    package=pkg.name,
                    license=pkg.license,
                    classification="unknown",
                    description=f"'{pkg.name}' has unknown/undetectable license.",
                ))

        return issues

    @staticmethod
    def _detect_site_packages() -> Path | None:
        """Find the current Python's site-packages directory."""
        try:
            import site
            dirs = site.getsitepackages()
            for d in dirs:
                p = Path(d)
                if p.is_dir() and any(p.glob("*.dist-info")):
                    return p
        except Exception:
            pass
        # Fallback: look relative to sys.executable
        exe = Path(sys.executable)
        for candidate in [
            exe.parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
            exe.parent / "Lib" / "site-packages",
        ]:
            if candidate.is_dir():
                return candidate
        return None
