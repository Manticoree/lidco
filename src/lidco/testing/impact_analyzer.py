"""
Test Impact Analyzer — Nx/Turborepo-style affected-test detection.

Given a set of changed source files, determine which test files are
likely affected by computing a reverse import graph.  Only affected
tests need to be re-run, saving time on large codebases.

Algorithm
---------
1. Parse all .py files in the project with the AST to build a
   module → imports mapping (forward graph).
2. Invert the graph to get  module → dependents.
3. Starting from the changed files, BFS through the inverted graph
   to collect all transitively-affected modules.
4. Filter the result to files that live under the test directories.
"""

from __future__ import annotations

import ast
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ChangeSet:
    files: list[str]


@dataclass
class ImpactResult:
    changed_files: list[str]
    affected_tests: list[str]
    skipped_tests: list[str]
    coverage_estimate: float  # fraction 0–1 of tests that need to run

    def get_minimal_test_command(
        self,
        runner: str = "python -m pytest",
        extra_flags: str = "-q",
    ) -> str:
        if not self.affected_tests:
            return f"{runner} {extra_flags} --collect-only -q  # no affected tests"
        paths = " ".join(sorted(set(self.affected_tests)))
        return f"{runner} {paths} {extra_flags}"


# ---------------------------------------------------------------------------
# AST import extractor
# ---------------------------------------------------------------------------

def _extract_imports(path: Path) -> list[str]:
    """Return a list of module names imported by *path*."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
    except Exception:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


def _path_to_module(path: Path, root: Path) -> str:
    """Convert an absolute path to a dotted module name relative to *root*."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return path.stem
    parts = list(rel.with_suffix("").parts)
    return ".".join(parts)


# ---------------------------------------------------------------------------
# TestImpactAnalyzer
# ---------------------------------------------------------------------------

class TestImpactAnalyzer:
    """
    Analyze which tests are affected by a set of changed files.

    Parameters
    ----------
    project_root : str | None
        Root of the project.  Defaults to current working directory.
    test_dirs : list[str] | None
        Directories to look for test files in.
        Defaults to ["tests", "test"].
    src_dirs : list[str] | None
        Directories considered source (non-test) code.
        Defaults to ["src"].
    """

    def __init__(
        self,
        project_root: str | None = None,
        test_dirs: list[str] | None = None,
        src_dirs: list[str] | None = None,
    ) -> None:
        self._root = Path(project_root) if project_root else Path.cwd()
        self._test_dirs = [
            self._root / d for d in (test_dirs or ["tests", "test"])
        ]
        self._src_dirs = [
            self._root / d for d in (src_dirs or ["src"])
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, changeset: ChangeSet) -> ImpactResult:
        """
        Return an ImpactResult for the given changeset.

        The analysis is purely static (AST-based), with no external deps.
        """
        changed_paths = [Path(f) for f in changeset.files]

        # Build the full import graph for the project
        all_py = list(self._root.rglob("*.py"))
        # forward_graph: file_path → set of imported module top-names
        forward_graph: dict[Path, set[str]] = {}
        for py in all_py:
            forward_graph[py] = set(_extract_imports(py))

        # Map module top-names → files that define them (rough heuristic)
        module_to_files: dict[str, list[Path]] = {}
        for py in all_py:
            mod = _path_to_module(py, self._root)
            top = mod.split(".")[0]
            module_to_files.setdefault(top, []).append(py)
            # also register the full module name
            module_to_files.setdefault(mod, []).append(py)

        # Inverted graph: file → files that import it
        inverted: dict[Path, set[Path]] = {py: set() for py in all_py}
        for py, imports in forward_graph.items():
            for imp in imports:
                for dep in module_to_files.get(imp, []):
                    inverted.setdefault(dep, set()).add(py)

        # BFS from changed files through inverted graph
        visited: set[Path] = set()
        queue = list(changed_paths)
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            for dependent in inverted.get(current, set()):
                if dependent not in visited:
                    queue.append(dependent)

        # Collect all test files
        all_tests = self._collect_tests()
        affected_tests = sorted(
            str(t) for t in all_tests if t in visited or t in changed_paths
        )
        skipped_tests = sorted(
            str(t) for t in all_tests if str(t) not in affected_tests
        )
        coverage_estimate = (
            len(affected_tests) / len(all_tests) if all_tests else 0.0
        )

        return ImpactResult(
            changed_files=changeset.files,
            affected_tests=affected_tests,
            skipped_tests=skipped_tests,
            coverage_estimate=coverage_estimate,
        )

    def analyze_since(self, git_ref: str = "HEAD~1") -> ImpactResult:
        """
        Determine changed files via `git diff --name-only <ref>` and analyze.
        Falls back to an empty changeset if git is unavailable.
        """
        try:
            proc = subprocess.run(
                ["git", "diff", "--name-only", git_ref],
                capture_output=True,
                text=True,
                cwd=str(self._root),
                timeout=10,
            )
            files = [
                str(self._root / f.strip())
                for f in proc.stdout.splitlines()
                if f.strip().endswith(".py")
            ]
        except Exception:
            files = []
        return self.analyze(ChangeSet(files=files))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _collect_tests(self) -> list[Path]:
        tests: list[Path] = []
        for test_dir in self._test_dirs:
            if test_dir.is_dir():
                for py in test_dir.rglob("test_*.py"):
                    tests.append(py)
                for py in test_dir.rglob("*_test.py"):
                    if py not in tests:
                        tests.append(py)
        return tests
