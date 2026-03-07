"""Module Not Found Advisor — fixes ModuleNotFoundError with fuzzy matching and pip suggestions.

Strategy (applied in order):
1. Check if the module is part of the Python standard library.
2. Look up the import name in the ``_KNOWN_ALIASES`` table (e.g. ``PIL`` → ``pillow``).
3. Levenshtein-match the module name against installed packages.
4. Fall back to the bare module name as the pip install target.

Usage::

    from lidco.core.module_advisor import advise_module_not_found, format_advice

    advice = advise_module_not_found("pydantics", installed_packages=None)
    if advice:
        print(format_advice(advice))
"""

from __future__ import annotations

import functools
import sys
from dataclasses import dataclass
from importlib.metadata import packages_distributions
from typing import Sequence


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModuleAdvice:
    """Structured advice for a ``ModuleNotFoundError``.

    Attributes:
        module_name: The import name that was not found.
        candidates:  Closest matching installed package names (Levenshtein).
        pip_install: Suggested ``pip install`` target, or ``None`` for stdlib.
        is_stdlib:   ``True`` when the module belongs to the standard library.
    """

    module_name: str
    candidates: list[str]
    pip_install: str | None
    is_stdlib: bool


# ---------------------------------------------------------------------------
# Known import-name → pip-package alias table
# ---------------------------------------------------------------------------

# Keys are lowercase for case-insensitive lookup.
# Only entries where the import name differs from the pip package name.
_KNOWN_ALIASES: dict[str, str] = {
    # Imaging
    "pil": "pillow",
    "image": "pillow",
    # Computer vision
    "cv2": "opencv-python",
    # Machine learning
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    # Data science / config
    "bs4": "beautifulsoup4",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "attr": "attrs",
    # Crypto / network
    "crypto": "pycryptodome",
    "openssl": "pyOpenSSL",
    # Database
    "psycopg2": "psycopg2-binary",
    "mysqldb": "mysqlclient",
    # Type checking
    "typing_extensions": "typing-extensions",
}

# Pre-computed lowercase key view (same dict, keys already lowercase).
_KNOWN_ALIASES_LOWER: dict[str, str] = _KNOWN_ALIASES


# ---------------------------------------------------------------------------
# Standard-library module set
# ---------------------------------------------------------------------------

# sys.stdlib_module_names is available from Python 3.10+
_STDLIB: frozenset[str] = frozenset(
    getattr(sys, "stdlib_module_names", frozenset())
)


# ---------------------------------------------------------------------------
# Cached live package list
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _get_installed_packages() -> list[str]:
    """Return installed top-level import names from the live environment.

    Result is cached for the lifetime of the process — package installations
    don't change during a debug session.
    """
    try:
        return list(packages_distributions().keys())
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Levenshtein distance
# ---------------------------------------------------------------------------


def _levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein (edit) distance between two strings.

    Uses the standard DP algorithm in O(|a| × |b|) time and O(min(|a|, |b|))
    space via the two-row rolling-array optimisation.
    """
    if len(a) < len(b):
        a, b = b, a
    # Now len(a) >= len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for ch_a in a:
        curr = [prev[0] + 1]
        for j, ch_b in enumerate(b):
            curr.append(min(
                curr[j] + 1,          # insertion
                prev[j + 1] + 1,      # deletion
                prev[j] + (ch_a != ch_b),  # substitution
            ))
        prev = curr
    return prev[-1]


# ---------------------------------------------------------------------------
# Candidate finder
# ---------------------------------------------------------------------------


def _find_candidates(
    module_name: str,
    known_packages: Sequence[str],
    max_distance: int = 3,
    top_k: int = 3,
) -> list[str]:
    """Return the closest package names from *known_packages* to *module_name*.

    Comparison is case-insensitive; original casing of *known_packages* entries
    is preserved in the returned list.  Packages whose distance exceeds
    *max_distance* are excluded.  At most *top_k* results are returned.
    Duplicate entries in *known_packages* are silently ignored.
    """
    module_lower = module_name.lower()
    seen: set[str] = set()
    scored: list[tuple[int, str]] = []
    for pkg in known_packages:
        if pkg in seen:
            continue
        seen.add(pkg)
        d = _levenshtein(module_lower, pkg.lower())
        if d <= max_distance:
            scored.append((d, pkg))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [pkg for _, pkg in scored[:top_k]]


# ---------------------------------------------------------------------------
# Core advisor
# ---------------------------------------------------------------------------


def advise_module_not_found(
    module_name: str,
    installed_packages: list[str] | None,
) -> ModuleAdvice:
    """Produce repair advice for a ``ModuleNotFoundError``.

    Args:
        module_name:        The bare import name that was not found (e.g. ``"PIL"``).
                            Sub-module paths like ``"numpy.linalg"`` are reduced to
                            their top-level component before matching.
        installed_packages: Explicit list of installed package names for
                            deterministic testing.  Pass ``None`` to query the live
                            environment via :mod:`importlib.metadata`.

    Returns:
        A :class:`ModuleAdvice` — always returned (never ``None``).
    """
    # Resolve sub-module paths to top-level (e.g. "numpy.linalg" → "numpy")
    top_level = module_name.split(".")[0] if module_name else module_name
    top_level_lower = top_level.lower()

    # 1. Standard library check (stdlib names are lowercase in sys.stdlib_module_names)
    if top_level_lower in _STDLIB or top_level in _STDLIB:
        return ModuleAdvice(
            module_name=module_name,
            candidates=[],
            pip_install=None,
            is_stdlib=True,
        )

    # 2. Known alias lookup (case-insensitive)
    if top_level_lower in _KNOWN_ALIASES_LOWER:
        pip_target = _KNOWN_ALIASES_LOWER[top_level_lower]
        return ModuleAdvice(
            module_name=module_name,
            candidates=[],
            pip_install=pip_target,
            is_stdlib=False,
        )

    # 3. Build installed-package list
    if installed_packages is None:
        pkgs = _get_installed_packages()
    else:
        pkgs = list(installed_packages)

    # 4. Levenshtein match against installed packages
    candidates = _find_candidates(top_level, pkgs)

    pip_target = candidates[0] if candidates else top_level

    return ModuleAdvice(
        module_name=module_name,
        candidates=candidates,
        pip_install=pip_target,
        is_stdlib=False,
    )


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_advice(advice: ModuleAdvice) -> str:
    """Format a :class:`ModuleAdvice` as a Markdown snippet.

    Returns a multi-line string suitable for display in the debug pipeline.
    """
    lines: list[str] = [f"[ModuleNotFoundError] No module named '{advice.module_name}'"]

    if advice.is_stdlib:
        lines.append(
            f"  '{advice.module_name}' is part of the Python standard library "
            f"and should always be available. "
            f"Check that you are running the correct Python interpreter "
            f"(python --version) and that the module name is spelled correctly."
        )
        return "\n".join(lines)

    if advice.candidates:
        lines.append(f"  Did you mean: {', '.join(advice.candidates)}?")

    if advice.pip_install:
        lines.append(f"  Fix: pip install {advice.pip_install}")
    elif not advice.candidates:
        lines.append("  No suggestions available. Verify the module name is spelled correctly.")

    return "\n".join(lines)
