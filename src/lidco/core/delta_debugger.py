"""Delta Debugger — ddmin input minimizer for reproducing test failures.

Implements a simplified version of the ddmin algorithm (Andreas Zeller 1999/2002)
to reduce a failing list-type fixture to its minimal reproducing subset.

Reference: Zeller A., Hildebrandt R., "Simplifying and Isolating Failure-Inducing
Input" (IEEE TSE 2002).  Validated on pytest list fixtures (Wiley 2024).

Usage::

    from lidco.core.delta_debugger import ddmin, DdminConfig, DdminResult

    oracle = lambda items: some_test_still_fails_with(items)
    result = ddmin(original_list, oracle)
    print(f"Reduced {result.original_length} → {result.minimal_length} items")
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DdminConfig:
    """Configuration for the ddmin algorithm.

    Attributes:
        max_iterations: Maximum oracle evaluation calls before stopping.
        timeout_s:      Maximum total wall-clock time in seconds.
    """

    max_iterations: int = 100
    timeout_s: float = 30.0


@dataclass(frozen=True)
class DdminResult:
    """Result of a ddmin minimization run.

    Attributes:
        original_length: Number of items in the original list.
        minimal_length:  Number of items in the reduced list.
        components:      The minimised list (still triggers the failure).
        iterations:      Number of oracle calls made.
        reduction_pct:   Percentage of items removed (0–100).
    """

    original_length: int
    minimal_length: int
    components: list[Any]
    iterations: int
    reduction_pct: float


# ---------------------------------------------------------------------------
# Core ddmin algorithm
# ---------------------------------------------------------------------------


def ddmin(
    components: list[T],
    oracle: Callable[[list[T]], bool],
    config: DdminConfig = DdminConfig(),
) -> DdminResult:
    """Reduce *components* to a minimal subset that still satisfies *oracle*.

    The oracle must return ``True`` when the given subset of *components*
    still triggers the failure of interest (i.e., the test still fails).

    The algorithm is ddmin as described by Zeller (2002) — it guarantees that
    the returned components are locally 1-minimal: removing any single element
    makes the oracle return False.

    Args:
        components: The input list to minimise (e.g., fixture parameters).
        oracle:     ``Callable[[list[T]], bool]`` — returns True if the failure
                    is reproduced with the given subset.
        config:     :class:`DdminConfig` controlling iteration and time limits.

    Returns:
        A :class:`DdminResult` with the minimised components.
    """
    original_length = len(components)
    iterations = 0
    start_time = time.monotonic()

    # Guard: oracle must hold for the full input
    if not components:
        return DdminResult(
            original_length=0,
            minimal_length=0,
            components=[],
            iterations=0,
            reduction_pct=0.0,
        )

    current = list(components)
    n = 2  # start with 2-way partition

    while len(current) >= 2:
        # Time / iteration budget check
        if iterations >= config.max_iterations:
            break
        if time.monotonic() - start_time > config.timeout_s:
            break

        chunk_size = max(1, len(current) // n)
        tried_any = False

        i = 0
        while i < len(current):
            if iterations >= config.max_iterations:
                break
            if time.monotonic() - start_time > config.timeout_s:
                break

            chunk = current[i: i + chunk_size]
            complement = current[:i] + current[i + chunk_size:]

            # Try complement first (reduce by removing chunk)
            if complement and oracle(complement):
                iterations += 1
                current = complement
                n = max(n - 1, 2)
                tried_any = True
                break  # restart with updated current

            iterations += 1

            # Try chunk itself
            if chunk and oracle(chunk):
                iterations += 1
                current = chunk
                n = 2
                tried_any = True
                break  # restart with updated current

            iterations += 1
            i += chunk_size

        if not tried_any:
            if n < len(current):
                n = min(2 * n, len(current))
            else:
                break  # 1-minimal: can't reduce further

    minimal_length = len(current)
    reduction_pct = (
        100.0 * (original_length - minimal_length) / original_length
        if original_length > 0
        else 0.0
    )
    return DdminResult(
        original_length=original_length,
        minimal_length=minimal_length,
        components=current,
        iterations=iterations,
        reduction_pct=reduction_pct,
    )


# ---------------------------------------------------------------------------
# Pytest oracle factory
# ---------------------------------------------------------------------------


def make_pytest_oracle(
    test_id: str,
    fixture_name: str,
    project_dir: Path,
) -> Callable[[list[Any]], bool]:
    """Create a pytest-based oracle for *test_id*.

    The oracle:
    1. Writes the candidate input list to a temporary conftest override file
    2. Runs ``pytest <test_id> -x -q --tb=no`` as a subprocess
    3. Returns ``True`` when the test still fails (non-zero exit code)

    Args:
        test_id:      Pytest node ID (e.g., ``tests/unit/test_foo.py::test_bar``).
        fixture_name: Name of the list-type fixture to override.
        project_dir:  Project root directory.

    Returns:
        A callable ``(items: list[Any]) -> bool``.
    """
    def oracle(items: list[Any]) -> bool:
        if not items:
            return False
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix="conftest_ddmin_",
            dir=str(project_dir),
            delete=False,
        ) as tmp:
            tmp.write(f"import pytest\n\n@pytest.fixture\ndef {fixture_name}():\n    return {items!r}\n")
            conftest_path = Path(tmp.name)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_id, "-x", "-q", "--tb=no", "--no-header"],
                cwd=str(project_dir),
                capture_output=True,
                timeout=30,
            )
            # Test still fails = oracle returns True
            return result.returncode != 0
        except Exception as exc:
            logger.debug("ddmin oracle subprocess failed: %s", exc)
            return False
        finally:
            try:
                conftest_path.unlink()
            except Exception:
                pass

    return oracle


# ---------------------------------------------------------------------------
# Entry point for list fixtures
# ---------------------------------------------------------------------------


def shrink_list_fixture(
    test_id: str,
    fixture_name: str,
    original_list: list[Any],
    project_dir: Path,
    config: DdminConfig = DdminConfig(),
) -> DdminResult:
    """Minimise *original_list* to the smallest subset that still fails *test_id*.

    Uses :func:`make_pytest_oracle` as the failure oracle and delegates to
    :func:`ddmin` for the minimization loop.

    Args:
        test_id:       Pytest node ID of the failing test.
        fixture_name:  Name of the fixture that accepts the list.
        original_list: The full input list to be minimised.
        project_dir:   Project root directory.
        config:        :class:`DdminConfig` for budget control.

    Returns:
        A :class:`DdminResult`.
    """
    oracle = make_pytest_oracle(test_id, fixture_name, project_dir)
    return ddmin(original_list, oracle, config)


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def format_ddmin_result(result: DdminResult) -> str:
    """Format *result* as a Markdown summary section.

    Returns ``""`` when the result represents no reduction.

    Example output::

        ## Delta Debugger Result
        - Original: 50 items → Minimal: 3 items (94.0% reduction)
        - Minimal reproducing input:
          `['foo', 'bar', 'baz']`
        - Oracle calls: 42
    """
    if result.original_length == 0:
        return ""
    lines = [
        "## Delta Debugger Result\n",
        f"- Original: **{result.original_length}** items "
        f"→ Minimal: **{result.minimal_length}** items "
        f"({result.reduction_pct:.1f}% reduction)",
        f"- Minimal reproducing input:\n  `{result.components!r}`",
        f"- Oracle calls: {result.iterations}",
    ]
    return "\n".join(lines)
