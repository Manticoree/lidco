"""SemVer — semantic versioning parse, compare, bump, and range matching (stdlib only).

Full SemVer 2.0.0 support: MAJOR.MINOR.PATCH[-pre][+build].
Supports simple range specs like ^1.2, ~2.3, >=1.0 <2.0, *, latest.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Any


class SemVerError(Exception):
    """Raised when a version string cannot be parsed or is invalid."""


_VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z\-]+(?:\.[0-9A-Za-z\-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z\-]+(?:\.[0-9A-Za-z\-]+)*))?$"
)

_LOOSE_RE = re.compile(
    r"^v?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?"
    r"(?:-(?P<pre>[0-9A-Za-z\-]+))?(?:\+(?P<build>[0-9A-Za-z\-]+))?$"
)


@total_ordering
@dataclass(frozen=True)
class Version:
    """An immutable semantic version."""

    major: int
    minor: int
    patch: int
    pre: str = ""       # pre-release identifier (e.g. "alpha.1")
    build: str = ""     # build metadata (ignored in comparisons)

    # ------------------------------------------------------------------ #
    # Construction                                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def parse(cls, text: str) -> "Version":
        """Parse a strict SemVer string."""
        text = text.strip().lstrip("v")
        m = _VERSION_RE.match(text)
        if not m:
            raise SemVerError(f"Invalid SemVer: {text!r}")
        return cls(
            major=int(m.group("major")),
            minor=int(m.group("minor")),
            patch=int(m.group("patch")),
            pre=m.group("pre") or "",
            build=m.group("build") or "",
        )

    @classmethod
    def parse_loose(cls, text: str) -> "Version":
        """Parse a loose version string (missing minor/patch default to 0)."""
        text = text.strip().lstrip("v")
        m = _LOOSE_RE.match(text)
        if not m:
            raise SemVerError(f"Cannot parse version: {text!r}")
        return cls(
            major=int(m.group("major") or 0),
            minor=int(m.group("minor") or 0),
            patch=int(m.group("patch") or 0),
            pre=m.group("pre") or "",
            build=m.group("build") or "",
        )

    @classmethod
    def from_tuple(cls, t: tuple) -> "Version":
        """Create from (major, minor, patch[, pre[, build]])."""
        if len(t) < 3:
            raise SemVerError("Tuple must have at least (major, minor, patch)")
        return cls(int(t[0]), int(t[1]), int(t[2]),
                   str(t[3]) if len(t) > 3 else "",
                   str(t[4]) if len(t) > 4 else "")

    # ------------------------------------------------------------------ #
    # String representation                                                #
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            base += f"-{self.pre}"
        if self.build:
            base += f"+{self.build}"
        return base

    def __repr__(self) -> str:
        return f"Version({self!s})"

    # ------------------------------------------------------------------ #
    # Comparison (build metadata ignored per SemVer spec)                 #
    # ------------------------------------------------------------------ #

    def _release_key(self) -> tuple:
        return (self.major, self.minor, self.patch)

    def _pre_key(self) -> tuple:
        """Pre-release versions have lower precedence than release."""
        if not self.pre:
            return (1,)   # no pre-release → higher
        parts = []
        for part in self.pre.split("."):
            parts.append((0, int(part)) if part.isdigit() else (1, part))
        return (0, *parts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._release_key() == other._release_key() and self.pre == other.pre

    def __lt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        if self._release_key() != other._release_key():
            return self._release_key() < other._release_key()
        return self._pre_key() < other._pre_key()

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.pre))

    # ------------------------------------------------------------------ #
    # Bumping                                                              #
    # ------------------------------------------------------------------ #

    def bump_major(self) -> "Version":
        return Version(self.major + 1, 0, 0)

    def bump_minor(self) -> "Version":
        return Version(self.major, self.minor + 1, 0)

    def bump_patch(self) -> "Version":
        return Version(self.major, self.minor, self.patch + 1)

    def with_pre(self, pre: str) -> "Version":
        return Version(self.major, self.minor, self.patch, pre, self.build)

    def release(self) -> "Version":
        """Strip pre-release and build metadata."""
        return Version(self.major, self.minor, self.patch)

    # ------------------------------------------------------------------ #
    # Predicates                                                           #
    # ------------------------------------------------------------------ #

    def is_stable(self) -> bool:
        return not self.pre and self.major > 0

    def is_prerelease(self) -> bool:
        return bool(self.pre)

    def is_compatible_with(self, other: "Version") -> bool:
        """True if self is backward-compatible with other (same major, self >= other)."""
        return self.major == other.major and self >= other

    # ------------------------------------------------------------------ #
    # Utility                                                              #
    # ------------------------------------------------------------------ #

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def next_versions(self) -> dict[str, "Version"]:
        return {
            "major": self.bump_major(),
            "minor": self.bump_minor(),
            "patch": self.bump_patch(),
        }


# ------------------------------------------------------------------ #
# Range matching                                                       #
# ------------------------------------------------------------------ #

class VersionRange:
    """Simple version range: ^X, ~X, >=X, >X, <=X, <X, =X, *, or compound."""

    _SINGLE_RE = re.compile(
        r"^\s*(?P<op>\^|~|>=|<=|>|<|=|==)?\s*(?P<ver>[\d][^\s]*)\s*$"
    )

    def __init__(self, spec: str) -> None:
        self._spec = spec.strip()
        self._predicates = self._parse(self._spec)

    def _parse(self, spec: str) -> list:
        if spec in ("*", "latest", ""):
            return [lambda v: True]

        predicates = []
        for part in spec.split():
            m = self._SINGLE_RE.match(part)
            if not m:
                continue
            op = m.group("op") or "="
            ver = Version.parse_loose(m.group("ver"))
            predicates.append(self._make_predicate(op, ver))
        return predicates or [lambda v: True]

    @staticmethod
    def _make_predicate(op: str, ver: Version):
        if op == "^":
            # Compatible: same major, >= ver
            return lambda v, _v=ver: v.major == _v.major and v >= _v
        if op == "~":
            # Approximately: same major+minor, >= ver
            return lambda v, _v=ver: v.major == _v.major and v.minor == _v.minor and v >= _v
        if op in ("=", "=="):
            return lambda v, _v=ver: v == _v
        if op == ">=":
            return lambda v, _v=ver: v >= _v
        if op == ">":
            return lambda v, _v=ver: v > _v
        if op == "<=":
            return lambda v, _v=ver: v <= _v
        if op == "<":
            return lambda v, _v=ver: v < _v
        return lambda v, _v=ver: v == _v

    def satisfies(self, version: Version | str) -> bool:
        if isinstance(version, str):
            version = Version.parse_loose(version)
        return all(pred(version) for pred in self._predicates)

    def filter(self, versions: list[Version]) -> list[Version]:
        return sorted(v for v in versions if self.satisfies(v))

    def max_satisfying(self, versions: list[Version]) -> Version | None:
        matches = self.filter(versions)
        return matches[-1] if matches else None

    def __repr__(self) -> str:
        return f"VersionRange({self._spec!r})"


# ------------------------------------------------------------------ #
# Convenience functions                                                #
# ------------------------------------------------------------------ #

def parse(text: str) -> Version:
    return Version.parse(text)


def compare(a: str, b: str) -> int:
    """Return -1, 0, or 1."""
    va, vb = Version.parse_loose(a), Version.parse_loose(b)
    if va < vb:
        return -1
    if va > vb:
        return 1
    return 0


def sort_versions(versions: list[str], reverse: bool = False) -> list[str]:
    parsed = [Version.parse_loose(v) for v in versions]
    return [str(v) for v in sorted(parsed, reverse=reverse)]


def latest(versions: list[str], stable_only: bool = False) -> str | None:
    if not versions:
        return None
    parsed = [Version.parse_loose(v) for v in versions]
    if stable_only:
        parsed = [v for v in parsed if v.is_stable()]
    if not parsed:
        return None
    return str(max(parsed))


def satisfies(version: str, spec: str) -> bool:
    return VersionRange(spec).satisfies(version)
