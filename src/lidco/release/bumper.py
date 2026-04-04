"""VersionBumper — parse, bump, and detect version bump types from commits (stdlib only)."""

from __future__ import annotations

import re


class VersionBumper:
    """Utilities for semantic version bumping based on commit messages."""

    _VERSION_RE = re.compile(
        r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
    )

    # Conventional-commit prefix patterns
    _MAJOR_PATTERNS = (
        re.compile(r"^BREAKING[\s\-]CHANGE", re.IGNORECASE),
        re.compile(r"!\s*:"),  # e.g. "feat!: ..."
    )
    _MINOR_PATTERNS = (
        re.compile(r"^feat(\(|:|\s)", re.IGNORECASE),
    )

    # ------------------------------------------------------------------ #
    # Parsing                                                              #
    # ------------------------------------------------------------------ #

    def current(self, version: str) -> tuple[int, int, int]:
        """Parse a version string into a (major, minor, patch) tuple.

        Raises ``ValueError`` if *version* is not a valid semver string.
        """
        m = self._VERSION_RE.match(version.strip())
        if not m:
            raise ValueError(f"Invalid version string: {version!r}")
        return int(m.group("major")), int(m.group("minor")), int(m.group("patch"))

    # ------------------------------------------------------------------ #
    # Bumping                                                              #
    # ------------------------------------------------------------------ #

    def bump_major(self, version: str) -> str:
        """Bump the major component, resetting minor and patch to 0."""
        major, _minor, _patch = self.current(version)
        return f"{major + 1}.0.0"

    def bump_minor(self, version: str) -> str:
        """Bump the minor component, resetting patch to 0."""
        major, minor, _patch = self.current(version)
        return f"{major}.{minor + 1}.0"

    def bump_patch(self, version: str) -> str:
        """Bump the patch component."""
        major, minor, patch = self.current(version)
        return f"{major}.{minor}.{patch + 1}"

    # ------------------------------------------------------------------ #
    # Auto-detection from commits                                          #
    # ------------------------------------------------------------------ #

    def detect_bump_type(self, commits: list[str]) -> str:
        """Detect the appropriate bump type from a list of commit messages.

        Returns ``"major"``, ``"minor"``, or ``"patch"``.
        """
        has_minor = False
        for msg in commits:
            stripped = msg.strip()
            for pat in self._MAJOR_PATTERNS:
                if pat.search(stripped):
                    return "major"
            for pat in self._MINOR_PATTERNS:
                if pat.search(stripped):
                    has_minor = True
        return "minor" if has_minor else "patch"

    def from_commits(self, commits: list[str], current_version: str) -> str:
        """Determine the next version from *commits* and *current_version*.

        Delegates to :meth:`detect_bump_type` then calls the appropriate bump method.
        """
        bump_type = self.detect_bump_type(commits)
        bumper = {
            "major": self.bump_major,
            "minor": self.bump_minor,
            "patch": self.bump_patch,
        }
        return bumper[bump_type](current_version)
